"""Generate every public file of the site from collected data: HTML pages (SEO / GEO / AEO
structured data, llms.txt, sitemap, robots, security.txt, manifest). All text is derived from
real collected data or from the documented methodology; nothing is placeholder content."""
import datetime as dt, html, json, os
from .store import load

NAV = [("overview", "Overview"), ("trends", "Trends"), ("sources", "Sources"),
       ("repos", "Repositories"), ("insights", "Insights"), ("about", "About &amp; links"),
       ("comments", "Comments")]
CSP = ("default-src 'none'; script-src 'self' https://giscus.app; style-src 'self' 'unsafe-inline' https://giscus.app; "
       "img-src 'self' data: https://avatars.githubusercontent.com; font-src 'self'; connect-src 'self'; "
       "frame-src https://giscus.app; base-uri 'none'; form-action 'none'; manifest-src 'self'")
AI_BOTS = ["GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "Claude-SearchBot",
           "PerplexityBot", "Google-Extended", "Applebot-Extended", "CCBot", "Bytespider", "Amazonbot", "cohere-ai"]
DOCS_TRAFFIC = "https://docs.github.com/rest/metrics/traffic"
DOCS_RATE = "https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api"
e = html.escape


def faq(cfg, s):
    t = s["totals"]
    return [
        ("How long does GitHub keep repository traffic data?",
         "GitHub keeps only the last 14 days of views and clones, and only the top 10 referrers and popular paths. "
         "Older days are discarded, so this dashboard stores a snapshot every day to keep a permanent history."),
        ("How often is the dashboard updated?",
         "A scheduled GitHub Actions workflow runs once a day. GitHub can take 24-48 hours to finalise a day's "
         "numbers, so the most recent days may still increase."),
        ("Does it show private repositories?",
         "No. Private repositories are never read, stored or published. Only public repositories appear here."),
        ("Why are clones much higher than views?",
         "Clones include automated traffic such as CI systems, mirrors and crawlers, so they are a weaker signal of "
         "human interest than views. Views and unique visitors are the better indicators."),
        ("What are unique visitors and why are they not added up over months?",
         "GitHub reports a deduplicated unique-visitor estimate for its 14-day window only. Adding daily uniques "
         "would count the same person repeatedly, so longer periods show views and clones, not summed uniques."),
        ("How is the repository score calculated?",
         "score = views in 30 days + 0.5 x clones in 30 days + 2 x unique visitors (14 days) + 3 x stars + 4 x forks. "
         "The top 20% of public, non-fork, non-archived repositories are marked top and the bottom 20% low."),
        ("How are API rate limits avoided?",
         "Active repositories are fetched daily, idle ones every 3 days and dormant ones weekly. Because GitHub returns "
         "a 14-day window on every call, no data is lost. Calls are sequential, and the run stops safely if the "
         "remaining hourly budget gets low."),
        ("Can I run this for my own GitHub account?",
         f"Yes. It is open source under the MIT license: fork github.com/{cfg['repo_full_name']}, add a "
         "GH_PAT secret with the repo scope, enable GitHub Pages on the main branch /docs folder and run the workflow."),
        ("Who can change this dashboard?",
         "Only the repository owner can change the code and data. The main branch is protected, forks cannot write "
         "to it, and the site runs under a strict content-security policy."),
        ("How many repositories are tracked right now?",
         f"{t['repos']} public repositories, with data through {s['last_data_day']}."),
    ]


def jsonld(cfg, prof, s, f, page="index"):
    base = cfg["site_url"]
    same = [l["url"] for l in (prof or {}).get("links", [])] + ([prof["url"]] if prof else [])
    org = {"@type": "Organization", "@id": base + "#publisher", "name": (prof or {}).get("name", "Publisher"),
           "url": next((l["url"] for l in (prof or {}).get("links", []) if l["kind"] == "website"), (prof or {}).get("url", base)),
           "sameAs": same}
    if prof and prof.get("avatar"):
        org["logo"] = prof["avatar"]
    graph = [
        org,
        {"@type": "WebSite", "@id": base + "#website", "url": base, "name": cfg["site_name"],
         "publisher": {"@id": base + "#publisher"}, "inLanguage": "en"},
        {"@type": "WebApplication", "@id": base + "#app", "name": cfg["site_name"], "url": base,
         "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)",
         "isAccessibleForFree": True, "license": "https://opensource.org/license/mit",
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
         "author": {"@id": base + "#publisher"}, "dateModified": s["generated"],
         "description": "Open-source dashboard that stores GitHub repository traffic (views, clones, referrers, stars) permanently."},
        {"@type": "Dataset", "@id": base + "#dataset", "name": "GitHub traffic history for public repositories",
         "description": "Daily views, clones, referrers and stars for public repositories, collected from the GitHub REST API.",
         "dateModified": s["generated"], "temporalCoverage": f"{s['first_data_day']}/{s['last_data_day']}",
         "license": "https://opensource.org/license/mit", "creator": {"@id": base + "#publisher"},
         "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json",
                           "contentUrl": base + "data/summary.json"}]},
    ]
    if page == "index":
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in f]})
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)


def head(cfg, title, desc, path, ld, extra=""):
    base = cfg["site_url"]
    url = base + path
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{e(CSP)}">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
<meta name="theme-color" content="#0b5fff">
<link rel="canonical" href="{e(url)}">
<link rel="icon" href="{base}assets/favicon.svg" type="image/svg+xml">
<link rel="manifest" href="{base}manifest.webmanifest">
<link rel="alternate" type="text/plain" href="{base}llms.txt" title="llms.txt">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(cfg['site_name'])}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{base}assets/og-image.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(cfg['site_name'])}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{base}assets/og-image.png">
<link rel="stylesheet" href="{base}assets/style.css">
<script type="application/ld+json">{ld}</script>{extra}
</head>"""


def header(cfg, prof, tabs=True, index=False):
    base = cfg["site_url"]
    href = (lambda k: f"#{k}") if index else (lambda k: f"{base}#{k}")
    nav = "".join(f'<a href="{href(k)}" data-tab="{k}">{v}</a>' for k, v in NAV)
    by = f"<small>by {e(prof['name'])}</small>" if prof else ""
    return f"""<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
<div class="wrap hdr">
<a class="brand" href="{base}"><svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="7" fill="#0b5fff"/><path d="M6 22l6-7 5 4 9-11" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Traffic Analytics{by}</span></a>
<nav id="tabs" aria-label="Dashboard sections">{nav}</nav>
<div class="actions"><button id="theme" class="icon" type="button" aria-label="Toggle dark mode" title="Toggle dark mode">&#9680;</button>
<a class="btn small" href="https://github.com/{cfg['repo_full_name']}" rel="noopener">Star on GitHub</a></div>
</div>
</header>"""


def footer(cfg, prof, s):
    base = cfg["site_url"]
    links = "".join(f'<li><a href="{e(l["url"])}" rel="me noopener">{e(l["label"])}</a></li>'
                    for l in (prof or {}).get("links", []))
    gh = f'<li><a href="{e(prof["url"])}" rel="me noopener">GitHub profile</a></li>' if prof else ""
    who = e(prof["name"]) if prof else "the maintainer"
    co = f" &middot; {e(prof['company'])}" if prof and prof.get("company") else ""
    return f"""<footer class="site-footer">
<div class="wrap fgrid">
<div><strong>{e(cfg['site_name'])}</strong>
<p>Permanent history of GitHub views, clones, referrers and stars for public repositories. Open source, free and login-free.</p>
<p class="mut">Built and maintained by {who}{co}.</p></div>
<div><h3>Dashboard</h3><ul>{''.join(f'<li><a href="{base}#{k}">{v}</a></li>' for k, v in NAV)}</ul></div>
<div><h3>Resources</h3><ul>
<li><a href="{base}about/">About</a></li><li><a href="{base}methodology/">Methodology</a></li>
<li><a href="{base}privacy/">Privacy</a></li><li><a href="{base}data/summary.json">Open data (JSON)</a></li>
<li><a href="{base}llms.txt">llms.txt</a></li><li><a href="{base}sitemap.xml">Sitemap</a></li>
<li><a href="https://github.com/{cfg['repo_full_name']}" rel="noopener">Source code</a></li>
<li><a href="https://github.com/{cfg['repo_full_name']}/discussions" rel="noopener">Discussions</a></li></ul></div>
<div><h3>Connect</h3><ul>{gh}{links}</ul></div>
</div>
<div class="wrap fbar"><span>&copy; {dt.date.today().year} {who}. MIT licensed.</span>
<span>Data through {e(s['last_data_day'])} &middot; updated {e(s['generated'][:10])} UTC</span>
<span class="mut">Not affiliated with, endorsed by or sponsored by GitHub, Inc. GitHub is a trademark of GitHub, Inc.</span></div>
</footer>"""


def static_facts(s):
    t = s["totals"]
    top = [r for r in s["repos"] if r["tier"] == "top"][:10]
    rows = "".join(f'<tr><td><a href="{e(r["url"])}" rel="noopener">{e(r["name"])}</a></td>'
                   f'<td>{r["v30"]:,}</td><td>{r["c30"]:,}</td><td>{r["stars"]:,}</td></tr>' for r in top)
    return (f'<!--STATIC_START--><section class="card" id="static-facts"><h2>Key facts</h2>'
            f'<p>As of {e(s["last_data_day"])}, this dashboard tracks {t["repos"]:,} public GitHub repositories. '
            f'In the last 30 days they received {t["views_30d"]:,} views and {t["clones_30d"]:,} clones, '
            f'and together hold {t["stars"]:,} stars and {t["forks"]:,} forks. Data comes directly from the GitHub '
            f'REST API and is stored every day, beyond GitHub&rsquo;s own 14-day window.</p>'
            f'<div class="wrapx"><table><caption>Top repositories by score</caption><thead><tr><th>Repository</th>'
            f'<th>Views 30d</th><th>Clones 30d</th><th>Stars</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'</section><!--STATIC_END-->')


def profile_card(prof):
    if not prof:
        return "<p>Profile information is collected automatically from GitHub.</p>"
    items = "".join(f'<li><a href="{e(l["url"])}" rel="me noopener"><b>{e(l["label"])}</b>'
                    f'<span class="mut">{e(l["url"].split("//", 1)[-1])}</span></a></li>' for l in prof["links"])
    feat = "".join(f'<li><a href="https://github.com/{e(prof["login"])}/{e(f["repo"])}" rel="noopener">{e(f["label"])}</a></li>'
                   for f in prof.get("featured", []))
    bits = [x for x in (prof.get("company"), prof.get("location")) if x]
    return (f'<div class="profile"><img src="{e(prof["avatar"] or "")}" alt="{e(prof["name"])} avatar" width="72" height="72" loading="lazy">'
            f'<div><h3>{e(prof["name"])}</h3>'
            + (f'<p class="mut">{" &middot; ".join(e(b) for b in bits)}</p>' if bits else "")
            + (f'<p>{e(prof["tagline"])}</p>' if prof.get("tagline") else "")
            + f'<p class="mut">On GitHub since {e(prof["created"])} &middot; {prof["public_repos"]:,} public repositories</p></div></div>'
            f'<h3>Links</h3><ul class="links">{items}<li><a href="{e(prof["url"])}" rel="me noopener"><b>GitHub</b>'
            f'<span class="mut">{e(prof["url"].split("//", 1)[-1])}</span></a></li></ul>'
            + (f'<h3>Featured project</h3><ul class="plain">{feat}</ul>' if feat else ""))


def build_index(cfg, prof, s):
    base = cfg["site_url"]
    f = faq(cfg, s)
    t = s["totals"]
    title = "GitHub Traffic Analytics Dashboard: Views, Clones & Referrers History"
    desc = (f"Free, open-source GitHub traffic analytics. Daily history of views, clones, referrers and stars "
            f"for {t['repos']} public repositories, beyond GitHub's 14-day limit. No login.")
    faq_html = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in f)
    body = f"""<body>
<script src="{base}assets/boot.js"></script>
{header(cfg, prof, index=True)}
<main id="main" class="wrap">
<section class="hero">
<div><h1>GitHub traffic analytics for every public repository</h1>
<p class="lead">Views, clones, referrers and stars with permanent daily history, because GitHub itself keeps only 14 days. Open to everyone, no login.</p></div>
<div class="fresh" id="fresh"><span class="dot"></span><span id="fresh-text">Data through {e(s['last_data_day'])}</span></div>
</section>

<section class="tab" id="tab-overview" data-title="Overview">
<div class="grid kpis" id="kpis" aria-live="polite"></div>
<div class="grid two">
<div class="card"><div class="bar"><h2>Views and clones, last 30 days</h2></div><div class="chartbox"><canvas id="c-overview" role="img" aria-label="Views and clones for the last 30 days"></canvas></div></div>
<div class="card"><h2>Highlights</h2><div id="highlights"></div><a class="more" href="#insights">All insights &rarr;</a></div>
</div>
<div class="grid two">
<div class="card"><h2>Top performers</h2><div class="wrapx"><table id="t-top"></table></div></div>
<div class="card"><h2>Needs attention</h2><div class="wrapx"><table id="t-low"></table></div></div>
</div>
{static_facts(s)}
</section>

<section class="tab" id="tab-trends" data-title="Trends">
<div class="card"><div class="bar"><h2>Traffic trend</h2>
<div class="seg" id="seg-period" role="group" aria-label="Granularity"><button data-p="daily" class="on">Daily</button><button data-p="weekly">Weekly</button><button data-p="monthly">Monthly</button><button data-p="yearly">Yearly</button></div>
<div class="seg" id="seg-range" role="group" aria-label="Range"><button data-r="30">30d</button><button data-r="90" class="on">90d</button><button data-r="365">1y</button><button data-r="0">All</button></div></div>
<div class="chartbox tall"><canvas id="c-trend" role="img" aria-label="Views and clones over time"></canvas></div>
<p class="note">GitHub finalises each day after 24-48 hours, so the newest days can still rise. Unique visitors are not summed over time (see methodology).</p></div>
<div class="grid two">
<div class="card"><h2>Views by weekday (90 days)</h2><div class="chartbox"><canvas id="c-weekday"></canvas></div></div>
<div class="card"><h2>Stars and forks over time</h2><div class="chartbox"><canvas id="c-stars"></canvas></div><p class="note" id="stars-note"></p></div>
</div>
<div class="card"><h2>New repositories per day (30 days)</h2><div class="chartbox"><canvas id="c-created"></canvas></div></div>
</section>

<section class="tab" id="tab-sources" data-title="Sources">
<div class="grid two">
<div class="card"><h2>Where visitors come from (latest 14 days)</h2><div class="chartbox tall"><canvas id="c-sources"></canvas></div><p class="note">GitHub reports the top 10 referrers per repository; they are summed across repositories.</p></div>
<div class="card"><h2>Google share over time</h2><div class="chartbox"><canvas id="c-google"></canvas></div><p class="note" id="google-note"></p>
<h2 class="sp">Most viewed pages</h2><div class="wrapx"><table id="t-paths"></table></div></div>
</div>
</section>

<section class="tab" id="tab-repos" data-title="Repositories">
<div class="card">
<div class="bar filters"><h2>All repositories</h2>
<input id="q" type="search" placeholder="Search name, topic or description (press /)" aria-label="Search repositories">
<select id="f-tier" aria-label="Tier"><option value="all">All tiers</option><option value="top">Top 20%</option><option value="mid">Middle</option><option value="low">Bottom 20%</option></select>
<select id="f-lang" aria-label="Language"><option value="">Any language</option></select>
<select id="f-sort" aria-label="Sort by"><option value="score">Score</option><option value="v30">Views 30d</option><option value="v7">Views 7d</option><option value="vall">Views all time</option><option value="c30">Clones 30d</option><option value="stars">Stars</option><option value="pushed">Last push</option><option value="created">Newest</option><option value="audit">Metadata score</option><option value="name">Name</option></select>
<button id="b-compare" type="button" class="btn small" disabled>Compare (0)</button>
<button id="b-csv" type="button" class="btn small ghost">Export CSV</button></div>
<div class="meta"><span id="cnt" class="mut"></span><span class="mut">Click a repository to open its details. Tick up to 4 to compare.</span></div>
<div class="wrapx"><table id="t-repos"></table></div>
<div class="pager" id="pager"></div>
</div>
</section>

<section class="tab" id="tab-insights" data-title="Insights">
<div class="card"><h2>Automatic insights</h2><p class="note">Generated from the collected numbers on every update. A sentence only appears when the data supports it.</p><div class="grid three" id="insights"></div></div>
<div class="grid two">
<div class="card"><h2>Languages (repos and 30-day views)</h2><div class="chartbox"><canvas id="c-lang"></canvas></div></div>
<div class="card"><h2>Top topics</h2><div class="chartbox"><canvas id="c-topics"></canvas></div></div>
</div>
<div class="card"><h2>Repository metadata audit</h2>
<p class="note">A transparent checklist, not a ranking guarantee: description, topics, license, homepage and recent activity. Average across repositories: <b id="audit-avg"></b>/100. Lowest scores first.</p>
<div class="wrapx"><table id="t-audit"></table></div></div>
</section>

<section class="tab" id="tab-about" data-title="About &amp; links">
<div class="grid two">
<div class="card"><h2>About the publisher</h2>{profile_card(prof)}<p class="note">Profile and links are fetched automatically from the public GitHub profile and its README every day.</p></div>
<div class="card"><h2>Frequently asked questions</h2>{faq_html}
<p><a href="{base}methodology/">Full methodology</a> &middot; <a href="{base}privacy/">Privacy</a> &middot; <a href="{base}data/summary.json">Open data</a></p></div>
</div>
</section>

<section class="tab" id="tab-comments" data-title="Comments">
<div class="card"><h2>Comments</h2><p class="note">Questions, feedback or ideas are welcome and links are allowed. Comments are stored in GitHub Discussions and need a free GitHub account to post. Reading is open to everyone.</p>
<div id="comments" data-repo="{e(cfg['repo_full_name'])}"></div>
<p class="note"><a href="https://github.com/{e(cfg['repo_full_name'])}/discussions" rel="noopener">Open the discussion board on GitHub</a></p></div>
</section>
</main>
<dialog id="repo-dialog" aria-labelledby="rd-title"><div id="rd"></div></dialog>
<button id="totop" class="totop" type="button" aria-label="Back to top" hidden>&uarr;</button>
{footer(cfg, prof, s)}
<script src="{base}assets/vendor/chart.umd.js"></script>
<script src="{base}assets/app.js"></script>
</body>
</html>"""
    return head(cfg, title, desc, "", jsonld(cfg, prof, s, f)) + "\n" + body


def subpage(cfg, prof, s, path, title, desc, h1, inner, page):
    base = cfg["site_url"]
    f = faq(cfg, s)
    crumbs = json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Dashboard", "item": base},
        {"@type": "ListItem", "position": 2, "name": h1, "item": base + path}]})
    ld = jsonld(cfg, prof, s, f, page=page)
    extra = f'\n<script type="application/ld+json">{crumbs}</script>'
    return (head(cfg, title, desc, path, ld, extra) +
            f'\n<body><script src="{base}assets/boot.js"></script>\n{header(cfg, prof)}\n<main id="main" class="wrap prose">'
            f'<nav class="crumbs" aria-label="Breadcrumb"><a href="{base}">Dashboard</a> / {e(h1)}</nav>'
            f'<h1>{e(h1)}</h1>{inner}</main>\n{footer(cfg, prof, s)}\n<script src="{base}assets/page.js"></script></body></html>')


def page_methodology(cfg, s):
    return f"""<p class="lead">How every number on this dashboard is collected, stored and calculated. Last reviewed with data through {e(s['last_data_day'])}.</p>
<h2>Data source</h2>
<p>All traffic numbers come from the official GitHub REST API <a href="{DOCS_TRAFFIC}" rel="noopener">repository traffic endpoints</a>: views, clones, popular referrers and popular paths. Repository metadata (stars, forks, topics, language, license, description, dates) comes from the repositories endpoint. Profile links come from the public GitHub profile, its social accounts and the profile README. Nothing is estimated, purchased or generated.</p>
<h2>Why history has to be stored</h2>
<p>GitHub keeps only the most recent 14 days of views and clones, and only the top 10 referrers and paths. This project saves what GitHub returns and merges it by date, so days that later fall out of GitHub's window remain available here. History starts on {e(s['first_data_day'])}, the first day of collection; earlier traffic cannot be recovered.</p>
<h2>Update schedule and rate limits</h2>
<p>A GitHub Actions workflow runs daily. Each API call returns a rolling 14-day window, so active repositories are fetched every day, idle ones every 3 days and dormant ones (no traffic for 45+ days) weekly, staggered by a stable hash of the repository name. Calls are sequential with a short delay, with retry and back-off, and the run stops and saves its progress if the remaining hourly budget falls below a safety floor. See GitHub's <a href="{DOCS_RATE}" rel="noopener">rate limit documentation</a>. Visitors of this site never call the GitHub API: the page reads static JSON files.</p>
<h2>Definitions</h2>
<ul><li><b>Views:</b> page views of a repository on GitHub, as reported by GitHub.</li>
<li><b>Unique visitors:</b> GitHub's deduplicated estimate for its 14-day window. It is shown per repository and summed across repositories on the overview, so a person who visits several repositories is counted more than once. It is not added across days.</li>
<li><b>Clones:</b> git clone operations, including automation such as CI, mirrors and crawlers.</li>
<li><b>Referrers:</b> the sites that sent visitors, limited by GitHub to the top 10 per repository.</li>
<li><b>Latest complete day:</b> the most recent UTC day before today. GitHub can take 24-48 hours to finalise a day, so it may increase.</li></ul>
<h2>Score and tiers</h2>
<p><code>score = views(30d) + 0.5 &times; clones(30d) + 2 &times; unique visitors(14d) + 3 &times; stars + 4 &times; forks</code>. Clones have a lower weight because they include automation. Among public, non-fork, non-archived repositories the top 20% are labelled <i>top</i> and the bottom 20% <i>low</i>. The weights are a transparent heuristic, not an official metric.</p>
<h2>Metadata audit</h2>
<p>Each repository receives a 0-100 checklist score: description present (25) and 40-160 characters (10), topics (2.5 points each up to 20; 8+ recommended), license (10), homepage URL (10) and a push within 90 days (15). It highlights gaps in public metadata; it does not predict search ranking.</p>
<h2>Insights</h2>
<p>Insight sentences are produced by fixed rules from the stored numbers (for example momentum, concentration, busiest weekday, spikes above 2.5 standard deviations). A rule stays silent when there is not enough data.</p>
<h2>Limitations</h2>
<ul><li>Traffic shown is what GitHub reports; bots and the owner's own visits may be included.</li>
<li>Only repositories owned by the publisher's account are tracked, and only public ones are published.</li>
<li>Referrer data is a rolling top-10 snapshot, so source totals are not exact lifetime sums.</li>
<li>New repositories appear after the next daily run.</li></ul>
<h2>Integrity and changes</h2>
<p>The code is open source under the MIT license at <a href="https://github.com/{e(cfg['repo_full_name'])}" rel="noopener">github.com/{e(cfg['repo_full_name'])}</a>. Only the owner can change it; every data update is a visible commit. Raw data is available as <a href="{cfg['site_url']}data/summary.json">JSON</a>.</p>"""


def page_privacy(cfg, s):
    return f"""<p class="lead">This site collects no personal data of its own. Details below.</p>
<h2>What this site does not do</h2>
<ul><li>No analytics, advertising or tracking scripts, and no cookies set by this site.</li>
<li>Private repositories are never read, stored or published.</li>
<li>No accounts or logins are needed to view anything.</li></ul>
<h2>What is stored in your browser</h2>
<p>Only your light or dark theme choice, saved locally in your browser. It is never sent anywhere.</p>
<h2>Published data</h2>
<p>The dashboard publishes public information about public repositories (names, descriptions, topics, stars, forks) together with the owner's traffic statistics, and the links found on the owner's public GitHub profile.</p>
<h2>Hosting</h2>
<p>The site is served by GitHub Pages. GitHub may process technical request data such as IP addresses under the <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener">GitHub General Privacy Statement</a>.</p>
<h2>Comments</h2>
<p>The Comments tab loads <a href="https://giscus.app" rel="noopener">giscus</a> in an embedded frame, only when you open that tab. Comments are public GitHub Discussions posts under the commenter's GitHub account and are subject to GitHub's terms. Posting requires signing in to GitHub; reading does not.</p>
<h2>Contact</h2>
<p>Use <a href="https://github.com/{e(cfg['repo_full_name'])}/discussions" rel="noopener">GitHub Discussions</a>. Security issues can be reported privately through the repository's <a href="https://github.com/{e(cfg['repo_full_name'])}/security/advisories/new" rel="noopener">security advisories</a>.</p>"""


def page_about(cfg, prof, s):
    t = s["totals"]
    who = e(prof["name"]) if prof else "the maintainer"
    return f"""<p class="lead">{cfg['site_name']} is a free, open-source tool that keeps the traffic history GitHub throws away after 14 days.</p>
<h2>Why it exists</h2>
<p>Repository owners need to know which projects attract visitors and where those visitors come from. GitHub only exposes two weeks of that data. This project saves it every day and shows daily, weekly, monthly and yearly trends, traffic sources, stars and forks, so decisions can be based on months of data.</p>
<h2>Who maintains it</h2>
{profile_card(prof)}
<p>Built and maintained by {who}. Currently it tracks {t['repos']:,} public repositories, collected from the GitHub REST API with data through {e(s['last_data_day'])}.</p>
<h2>Editorial and data policy</h2>
<ul><li>Every number is taken from the GitHub API or computed from it with the formulas on the <a href="{cfg['site_url']}methodology/">methodology page</a>.</li>
<li>No placeholder, simulated or purchased data. Missing values are shown as a dash.</li>
<li>Private repositories are excluded entirely.</li>
<li>Corrections and questions are welcome through <a href="https://github.com/{e(cfg['repo_full_name'])}/discussions" rel="noopener">GitHub Discussions</a>.</li></ul>"""


def build_all(cfg):
    s = load("docs/data/summary.json")
    prof = load("docs/data/profile.json")
    base = cfg["site_url"]
    w = lambda p, t: (os.makedirs(os.path.dirname("docs/" + p) or "docs", exist_ok=True), open("docs/" + p, "w", encoding="utf-8").write(t))
    w("index.html", build_index(cfg, prof, s))
    w("methodology/index.html", subpage(cfg, prof, s, "methodology/", "Methodology: how GitHub traffic data is collected and calculated",
        "How views, clones, referrers, scores and insights are collected from the GitHub API, stored beyond the 14-day limit and calculated.",
        "Methodology", page_methodology(cfg, s), "methodology"))
    w("privacy/index.html", subpage(cfg, prof, s, "privacy/", "Privacy policy: no tracking, no cookies",
        "This dashboard sets no cookies and runs no analytics. Private repositories are never collected. Details on hosting and comments.",
        "Privacy", page_privacy(cfg, s), "privacy"))
    w("about/index.html", subpage(cfg, prof, s, "about/", "About the GitHub Traffic Analytics Dashboard and its maintainer",
        "Who maintains the dashboard, why it exists and the editorial and data policy behind every number.",
        "About", page_about(cfg, prof, s), "about"))
    nf = subpage(cfg, prof, s, "404.html", "Page not found", "This page does not exist.", "Page not found",
        f'<p>The page you requested was not found. Go to the <a href="{base}">dashboard</a>.</p>', "404")
    w("404.html", nf.replace('content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1"', 'content="noindex"'))

    t = s["totals"]
    top = [r for r in s["repos"] if r["tier"] == "top"][:10]
    llms = f"""# {cfg['site_name']}

> Free, open-source dashboard that stores GitHub repository traffic (views, clones, referrers, stars) permanently, beyond GitHub's 14-day limit. Open to everyone, no login. Public repositories only. Data through {s['last_data_day']}, updated {s['generated'][:10]}.

## Pages
- [Dashboard]({base}): overview, trends, sources, repositories, insights, links, comments
- [Methodology]({base}methodology/): data source, definitions, formulas, limitations
- [About]({base}about/): maintainer, purpose, editorial and data policy
- [Privacy]({base}privacy/): no cookies or tracking
- [Source code](https://github.com/{cfg['repo_full_name']}): MIT licensed

## Data
- [summary.json]({base}data/summary.json): aggregated statistics, repository table, insights
- [series.json]({base}data/series.json): daily views and clones per repository (sparse)
- [profile.json]({base}data/profile.json): publisher profile and public links

## Key facts
- Tracked public repositories: {t['repos']}
- Views, last 30 days: {t['views_30d']}; clones: {t['clones_30d']}; stars: {t['stars']}; forks: {t['forks']}
- Source of data: GitHub REST API traffic endpoints ({DOCS_TRAFFIC})
"""
    w("llms.txt", llms)
    rows = "\n".join(f"- {r['name']}: {r['v30']} views, {r['c30']} clones, {r['stars']} stars (30 days) - {r['url']}" for r in top)
    qa = "\n\n".join(f"### {q}\n{a}" for q, a in faq(cfg, s))
    w("llms-full.txt", llms + f"\n## Top repositories by score\n{rows}\n\n## FAQ\n\n{qa}\n")
    bots = "".join(f"User-agent: {b}\nAllow: /\n\n" for b in AI_BOTS)
    w("robots.txt", f"User-agent: *\nAllow: /\n\n{bots}Sitemap: {base}sitemap.xml\n")
    d = s["generated"][:10]
    urls = "".join(f"<url><loc>{base}{p}</loc><lastmod>{d}</lastmod><changefreq>{c}</changefreq></url>"
                   for p, c in (("", "daily"), ("about/", "monthly"), ("methodology/", "monthly"), ("privacy/", "yearly")))
    w("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    exp = (dt.date.today() + dt.timedelta(days=365)).isoformat()
    w(".well-known/security.txt", f"Contact: https://github.com/{cfg['repo_full_name']}/security/advisories/new\nExpires: {exp}T00:00:00.000Z\nPreferred-Languages: en\nCanonical: {base}.well-known/security.txt\n")
    w("manifest.webmanifest", json.dumps({"name": cfg["site_name"], "short_name": "Traffic Analytics", "start_url": base,
        "display": "standalone", "background_color": "#ffffff", "theme_color": "#0b5fff",
        "icons": [{"src": base + "assets/favicon.svg", "sizes": "any", "type": "image/svg+xml"}]}))
    w(".nojekyll", "")
