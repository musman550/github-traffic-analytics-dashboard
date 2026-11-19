"""Long-form, crawlable pages: weekly reports, guides, extended FAQ and data documentation.
Every figure is computed from stored data; guides contain verified, documented facts only."""
import datetime as dt, html, os
from .store import load

e = html.escape
PUBLISHED = "2026-11-14"
DOCS_TRAFFIC = "https://docs.github.com/rest/metrics/traffic"
DOCS_RATE = "https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api"
DOCS_CRON = "https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule"


def _d(s):
    return dt.date.fromisoformat(s)


def fmt_d(d):
    return f"{d.day} {d.strftime('%b %Y')}"


# ---------------------------------------------------------------- weekly reports
def weekly_reports(s):
    """One report per fully collected ISO week (Monday-Sunday)."""
    series = load("docs/data/series.json", {"repos": {}})["repos"]
    first, last = _d(s["first_data_day"]), _d(s["last_data_day"])
    created = [r["created"] for r in s["repos"] if r["created"]]
    mon = first + dt.timedelta(days=(7 - first.weekday()) % 7)
    out = []

    def week(start):
        days = [(start + dt.timedelta(days=i)).isoformat() for i in range(7)]
        per_repo = {}
        for name, ser in series.items():
            v = sum(ser["views"].get(d, [0, 0])[0] for d in days)
            c = sum(ser["clones"].get(d, [0, 0])[0] for d in days)
            if v or c:
                per_repo[name] = (v, c)
        dv = [sum(ser["views"].get(d, [0, 0])[0] for ser in series.values()) for d in days]
        dc = [sum(ser["clones"].get(d, [0, 0])[0] for ser in series.values()) for d in days]
        return {"start": start, "days": days, "views": sum(dv), "clones": sum(dc), "dv": dv, "dc": dc, "repos": per_repo}

    while mon + dt.timedelta(days=6) <= last:
        w = week(mon)
        prev = week(mon - dt.timedelta(days=7)) if mon - dt.timedelta(days=7) >= first else None
        w["prev"] = prev
        w["created"] = sum(1 for c in created if w["days"][0] <= c <= w["days"][-1])
        out.append(w)
        mon += dt.timedelta(days=7)
    return out[::-1]


def report_slug(w):
    return w["start"].isoformat()


def report_title(w):
    end = w["start"] + dt.timedelta(days=6)
    return f"Weekly GitHub traffic report: {fmt_d(w['start'])} to {fmt_d(end)}"


def _chg(a, b):
    if not b:
        return ""
    p = round((a - b) * 100 / b)
    return f" ({'+' if p >= 0 else ''}{p}% vs the previous week)"


def report_summary(w):
    end = w["start"] + dt.timedelta(days=6)
    best = max(range(7), key=lambda i: w["dv"][i])
    top = sorted(w["repos"].items(), key=lambda x: -x[1][0])
    withv = [t for t in top if t[1][0] > 0]
    txt = (f"From {fmt_d(w['start'])} to {fmt_d(end)}, public repositories received {w['views']:,} views"
           f"{_chg(w['views'], w['prev']['views'] if w['prev'] else 0)} and {w['clones']:,} clones"
           f"{_chg(w['clones'], w['prev']['clones'] if w['prev'] else 0)}. ")
    if w["views"]:
        txt += (f"The busiest day was {_d(w['days'][best]).strftime('%A')} {w['days'][best]} with {w['dv'][best]:,} views. "
                f"{len(withv)} repositories received at least one view")
        if withv:
            txt += f", and {withv[0][0]} led with {withv[0][1][0]:,} ({round(withv[0][1][0] * 100 / w['views'])}% of the total)"
        txt += ". "
    txt += f"{w['created']} new repositories were created during the week."
    return txt


def report_body(cfg, s, w, base):
    end = w["start"] + dt.timedelta(days=6)
    top = [t for t in sorted(w["repos"].items(), key=lambda x: (-x[1][0], -x[1][1])) if t[1][0] > 0][:10]
    url = {r["name"]: r["url"] for r in s["repos"]}
    rows = "".join(f'<tr><td><a href="{e(url.get(n, "#"))}" rel="noopener">{e(n)}</a></td><td>{v:,}</td><td>{c:,}</td></tr>' for n, (v, c) in top)
    days = "".join(f"<tr><td>{d} ({_d(d).strftime('%a')})</td><td>{v:,}</td><td>{c:,}</td></tr>" for d, v, c in zip(w["days"], w["dv"], w["dc"]))
    cmp = ""
    if w["prev"]:
        cmp = (f'<tr><td>Previous week</td><td>{w["prev"]["views"]:,}</td><td>{w["prev"]["clones"]:,}</td></tr>')
    return (f'<p class="lead">{e(report_summary(w))}</p>'
            f'<h2>Totals</h2><div class="wrapx"><table><thead><tr><th>Period</th><th>Views</th><th>Clones</th></tr></thead><tbody>'
            f'<tr><td>{fmt_d(w["start"])} to {fmt_d(end)}</td><td>{w["views"]:,}</td><td>{w["clones"]:,}</td></tr>{cmp}</tbody></table></div>'
            f'<h2>Views and clones by day</h2><div class="wrapx"><table><thead><tr><th>Day</th><th>Views</th><th>Clones</th></tr></thead><tbody>{days}</tbody></table></div>'
            f'<h2>Most viewed repositories</h2>'
            + (f'<div class="wrapx"><table><thead><tr><th>Repository</th><th>Views</th><th>Clones</th></tr></thead><tbody>{rows}</tbody></table></div>' if rows else '<p>No repository received a view this week.</p>') +
            f'<p class="note">Clones include automation such as CI systems and crawlers. Numbers come from the GitHub REST API and follow the '
            f'<a href="{base}methodology/">methodology</a>. <a href="{base}reports/">All weekly reports</a>.</p>')


def reports_index_body(cfg, reports, base):
    if not reports:
        return ('<p class="lead">The first weekly report is published once a full Monday-to-Sunday week of data has been collected.</p>')
    items = "".join(f'<li><a href="{base}reports/{report_slug(w)}/">{e(report_title(w))}</a> '
                    f'<span class="mut">{w["views"]:,} views, {w["clones"]:,} clones</span></li>' for w in reports)
    return (f'<p class="lead">One report per completed week, generated automatically from collected GitHub traffic. '
            f'Subscribe with the <a href="{base}feed.xml">Atom feed</a>.</p><ul class="plain">{items}</ul>')


def atom_feed(cfg, prof, reports, base, generated):
    ents = ""
    for w in reports[:25]:
        end = (w["start"] + dt.timedelta(days=6)).isoformat()
        ents += (f'<entry><id>{base}reports/{report_slug(w)}/</id><title>{e(report_title(w))}</title>'
                 f'<link href="{base}reports/{report_slug(w)}/"/><updated>{end}T23:59:59Z</updated>'
                 f'<summary>{e(report_summary(w))}</summary></entry>')
    who = e(prof["name"]) if prof else "Publisher"
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">'
            f'<id>{base}</id><title>{e(cfg["site_name"])}: weekly reports</title><link href="{base}feed.xml" rel="self"/>'
            f'<link href="{base}reports/"/><updated>{generated}</updated><author><name>{who}</name></author>{ents}</feed>\n')


# ---------------------------------------------------------------- FAQ
def faq_extra():
    return [
        ("Can I see who visited my GitHub repository?",
         "No. GitHub's traffic data is aggregate only: counts of views and clones, unique-visitor estimates and referrer "
         "sites. It does not identify individual visitors."),
        ("Who can see repository traffic on GitHub?",
         "Only people with push access to a repository can read its traffic data, in the Insights tab or through the REST API."),
        ("Why does github.com appear as a referrer?",
         "It usually means visitors arrived from another page on GitHub, such as a profile, search results or a different repository."),
        ("How is this different from GitHub's Insights tab?",
         "Insights shows only the last 14 days for one repository at a time. This dashboard stores every day, combines all "
         "your public repositories and adds trends, sources, rankings and exports."),
        ("How do I export the data?",
         "Download repos.csv and daily.csv, or the JSON files, from the data page. They are static files that update daily."),
        ("What happens if an update fails?",
         "The status page shows every collection run. A failed or partial run creates an alert issue, and a daily watchdog "
         "checks that the published data is fresh. Because each GitHub call returns 14 days, a missed day is recovered by the next run."),
        ("Can I install the dashboard as an app?",
         "Yes. Browsers that support installable web apps offer an install option, and the last loaded data stays available offline."),
        ("Does AI change my repositories?",
         "An optimizer proposes better descriptions, topics and a README summary for the owner's public tool repositories. "
         "Topics are only added, README changes arrive as pull requests, every change is logged on the optimizer page and a traffic drop triggers a rollback."),
        ("Is this affiliated with GitHub?",
         "No. It is an independent open-source project that uses the public GitHub REST API."),
    ]


# ---------------------------------------------------------------- guides
SNIPPET_PY = '''import json, os, requests

TOKEN = os.environ["GH_PAT"]               # token with push access to the repository
REPO = "owner/repo"
H = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}

def fetch(kind):                           # kind: "views" or "clones"
    r = requests.get(f"https://api.github.com/repos/{REPO}/traffic/{kind}", headers=H, timeout=30)
    r.raise_for_status()
    return r.json()[kind]                  # [{"timestamp", "count", "uniques"}, ...]

history = json.load(open("traffic.json")) if os.path.exists("traffic.json") else {"views": {}, "clones": {}}
for kind in ("views", "clones"):
    for row in fetch(kind):
        history[kind][row["timestamp"][:10]] = [row["count"], row["uniques"]]   # upsert by day
json.dump(history, open("traffic.json", "w"), indent=1, sort_keys=True)'''

SNIPPET_YML = '''name: Save traffic
on:
  schedule:
    - cron: "17 2 * * *"
  workflow_dispatch:
permissions:
  contents: write
jobs:
  save:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install requests && python save_traffic.py
        env:
          GH_PAT: ${{ secrets.GH_PAT }}
      - run: |
          git config user.name "traffic-bot"
          git config user.email "traffic-bot@users.noreply.github.com"
          git add traffic.json
          git diff --cached --quiet || git commit -m "traffic: $(date -u +%F)"
          git push'''


def guide_14_days(cfg, base):
    repo = cfg["repo_full_name"]
    return f"""<p class="lead">GitHub shows repository views and clones for the last 14 days only. This guide explains how to keep them for as long as you want, with free tools.</p>
<div class="card"><h2>Key takeaways</h2><ul><li>GitHub keeps 14 days of views and clones and the top 10 referrers and paths; older data is gone.</li>
<li>You need push access and a token; save each day by date (upsert), never append.</li>
<li>A scheduled GitHub Actions workflow plus a JSON file in the repository is enough, at no cost.</li></ul></div>
<h2>What GitHub keeps</h2>
<p>The Insights &rarr; Traffic page and the <a href="{DOCS_TRAFFIC}" rel="noopener">traffic REST endpoints</a> return the previous 14 days of views and clones, plus the top 10 referring sites and the top 10 popular paths. Anything older is no longer available, so history has to be saved by you.</p>
<h2>Step 1: get a token</h2>
<p>Only people with push access can read traffic. A classic personal access token with the <code>repo</code> scope works; for a fine-grained token, GitHub documents read access to the repository's <i>Administration</i> permission for these endpoints. Store it as a secret (for Actions: <code>GH_PAT</code>), never in a web page or in code.</p>
<h2>Step 2: read the endpoints</h2>
<ul><li><code>GET /repos/{{owner}}/{{repo}}/traffic/views</code>: total and unique views per day</li>
<li><code>GET /repos/{{owner}}/{{repo}}/traffic/clones</code>: total and unique clones per day</li>
<li><code>GET /repos/{{owner}}/{{repo}}/traffic/popular/referrers</code>: top 10 referring sites</li>
<li><code>GET /repos/{{owner}}/{{repo}}/traffic/popular/paths</code>: top 10 popular paths</li></ul>
<h2>Step 3: merge by day, do not append</h2>
<p>Each call returns a rolling window, and GitHub can revise recent days for 24-48 hours. Save each day under its date and overwrite it on the next run (an upsert). This keeps history correct and lets you fetch less often than daily without losing data, as long as you run at least every 14 days.</p>
<pre><code>{e(SNIPPET_PY)}</code></pre>
<h2>Step 4: run it on a schedule</h2>
<p>A <a href="{DOCS_CRON}" rel="noopener">scheduled GitHub Actions workflow</a> can run the script daily and commit the JSON file back to the repository.</p>
<pre><code>{e(SNIPPET_YML)}</code></pre>
<h2>Step 5: stay inside rate limits</h2>
<p>Authenticated REST requests have an hourly allowance (see GitHub's <a href="{DOCS_RATE}" rel="noopener">rate limit documentation</a>). Four calls per repository per run is small for a handful of repositories, but hundreds of repositories need care: call sequentially, check the <code>x-ratelimit-remaining</code> header, and fetch idle repositories less often.</p>
<h2>Skip the work: use this dashboard</h2>
<p>This open-source project does all of the above for every public repository of an account and adds charts, rankings and exports. Fork <a href="https://github.com/{e(repo)}" rel="noopener">{e(repo)}</a>, add the <code>GH_PAT</code> secret, enable GitHub Pages on the <code>docs</code> folder and run the workflow. See the <a href="{base}methodology/">methodology</a> for details.</p>"""


def guide_api(cfg, base):
    return f"""<p class="lead">A compact reference for GitHub's repository traffic endpoints: what each returns, who can call it and what the limits are.</p>
<div class="card"><h2>Key takeaways</h2><ul><li>Four endpoints: views, clones, popular referrers and popular paths.</li>
<li>All cover the last 14 days; referrers and paths return only the top 10.</li>
<li>Uniques are deduplicated within the window only and must not be summed across days.</li></ul></div>
<h2>Endpoints</h2>
<div class="wrapx"><table><thead><tr><th>Endpoint</th><th>Returns</th><th>Window</th></tr></thead><tbody>
<tr><td><code>/repos/{{owner}}/{{repo}}/traffic/views</code></td><td>count, uniques and a list of daily {{timestamp, count, uniques}}</td><td>14 days</td></tr>
<tr><td><code>/repos/{{owner}}/{{repo}}/traffic/clones</code></td><td>count, uniques and a list of daily {{timestamp, count, uniques}}</td><td>14 days</td></tr>
<tr><td><code>/repos/{{owner}}/{{repo}}/traffic/popular/referrers</code></td><td>list of {{referrer, count, uniques}}</td><td>14 days, top 10</td></tr>
<tr><td><code>/repos/{{owner}}/{{repo}}/traffic/popular/paths</code></td><td>list of {{path, title, count, uniques}}</td><td>14 days, top 10</td></tr>
</tbody></table></div>
<p>The views and clones endpoints accept a <code>per</code> parameter to choose daily or weekly buckets. Always read the official <a href="{DOCS_TRAFFIC}" rel="noopener">GitHub documentation</a> for the current contract.</p>
<h2>Access</h2>
<p>You need push access to the repository. Send a token in the <code>Authorization: Bearer</code> header and request <code>application/vnd.github+json</code>. Private repositories require a token that can read them; this dashboard never collects private repositories.</p>
<h2>Interpreting the numbers</h2>
<ul><li><b>uniques</b> are deduplicated only inside the returned window, so do not add them across days.</li>
<li><b>clones</b> include CI systems, mirrors and crawlers.</li>
<li>Recent days can still change for 24-48 hours.</li>
<li>Referrers and paths are a top-10 snapshot, not a complete log.</li></ul>
<h2>Limits</h2>
<p>Requests count against GitHub's REST rate limit, described in the <a href="{DOCS_RATE}" rel="noopener">rate limit documentation</a>. Responses include <code>x-ratelimit-remaining</code> and <code>x-ratelimit-reset</code>; stop when the remaining budget is low. Because a call returns 14 days, fetching a quiet repository every few days loses nothing.</p>
<h2>Keeping history</h2>
<p>See <a href="{base}guides/keep-github-traffic-history/">how to keep GitHub traffic data beyond 14 days</a>.</p>"""


def data_page(cfg, s, base):
    t = s["totals"]
    rows = [
        ("summary.json", "Dashboard data: totals, daily/weekly/monthly/yearly series, repository table, sources, insights, languages, topics. Daily rows are [date, views, unique views (summed per repo), clones, unique clones (summed)]."),
        ("series.json", 'Per repository history: {"repos": {name: {"views": {"YYYY-MM-DD": [count, uniques]}, "clones": {...}, "win": {...}}}}. Days without traffic are omitted.'),
        ("repos.json", "Public repository metadata: description, topics, language, license, stars, forks, dates."),
        ("sources.json", "Referrer snapshots: by_date totals (14-day windows) and top referrers and paths per repository."),
        ("totals_history.json", "Daily totals: [date, repositories, stars, forks, watchers, open issues]."),
        ("profile.json", "Publisher profile and public links collected from GitHub."),
        ("repos.csv", "Repository table as CSV (views, clones, stars, language, license, score)."),
        ("daily.csv", "Daily views and clones across all repositories as CSV."),
        ("health.json", "Status of the last collection run."),
    ]
    tr = "".join(f'<tr><td><a href="{base}data/{n}">{n}</a></td><td style="white-space:normal;text-align:left">{e(d)}</td></tr>' for n, d in rows)
    return f"""<p class="lead">All numbers on this dashboard are published as static files. They are updated daily and free to use under the MIT license; attribution is appreciated.</p>
<h2>Files</h2><div class="wrapx"><table><thead><tr><th>File</th><th>Contents</th></tr></thead><tbody>{tr}</tbody></table></div>
<h2>Current snapshot</h2><p>{t['repos']:,} public repositories; data from {e(s['first_data_day'])} through {e(s['last_data_day'])}; generated {e(s['generated'])}.</p>
<h2>Example</h2><pre><code>import requests
s = requests.get("{base}data/summary.json", timeout=30).json()
print(s["totals"]["views_30d"], "views in the last 30 days")</code></pre>
<h2>Badges</h2><p>Endpoint files for <a href="https://shields.io/badges/endpoint-badge" rel="noopener">Shields.io</a> are available at <code>{base}badges/views-30d.json</code>, <code>repos.json</code>, <code>stars.json</code> and <code>clones-30d.json</code>.</p>
{cite_block(cfg, s, load("docs/data/profile.json"), base)}
<h2>Notes</h2><ul><li>Only public repositories are included.</li><li>Clones include automation.</li><li>See the <a href="{base}methodology/">methodology</a> for definitions and limits.</li></ul>"""


# ---------------------------------------------------------------- changelog
CHANGELOG = [
    ("5.0.0", "2026-11-15", [
        "AI optimizer: improves repository descriptions and topics and proposes README summaries by pull request",
        "Multi-provider router for open-weight models (keyless OVHcloud and Pollinations tiers, plus Groq, Cerebras, GitHub Models, OpenRouter, Hugging Face, Mistral, Cloudflare when keys exist) with cooldowns, daily budgets, caching, stub detection and automatic fallback to rules",
        "Safety: invalid parts are dropped, grounded topics, no links or hype, number checks, scored fact-check by a different model, junk-topic cleanup, README pull requests with auto-merge window and automatic rollback after a traffic drop",
        "Public optimizer page and dashboard tab with provider health and a full change log; fixed a rate-limit bug where the search budget was mistaken for the core budget",
    ]),
    ("4.0.0", "2026-11-15", [
        "Faster first paint: scripts load deferred and static assets are versioned, so updates never serve stale files",
        "Installable web app with offline cache for the last loaded data",
        "Crawlable repositories index with descriptions, languages, stars and traffic",
        "Public status page with the history of collection runs, plus alerts for failed runs, traffic spikes and finished weekly reports (GitHub issues, optional Telegram) and a daily watchdog",
        "Command palette (Ctrl/Cmd+K), chart PNG download and accessible data tables",
        "Social preview images for weekly reports, previous/next report links, changelog, CITATION.cff and search-engine verification hooks",
    ]),
    ("3.0.0", "2026-11-15", [
        "Fixed charts breaking after a theme change and the wrong tab after closing a repository dialog",
        "Statistics now end two days back because GitHub finalises days after 24-48 hours",
        "Fixed fetch scheduling: clones no longer make every repository active; a full refresh dropped from 1,072 to about 680 API calls and normal days use roughly 250-350",
        "Settings panel, shareable filter URLs, gainers and decliners, 7-day average, calendar heatmap",
        "Weekly reports with Atom feed, FAQ, two guides, open data page, CSV downloads and badge endpoints",
        "Pre-publish site audit, CI, pinned GitHub Actions and IndexNow notifications",
    ]),
    ("2.0.0", "2026-11-14", [
        "Tabbed dashboard with repository detail view, compare, filters, pagination and CSV export",
        "Automatic profile links, insights, metadata audit and richer structured data",
        "Private repositories removed from collection and publication entirely",
    ]),
    ("1.0.0", "2026-11-14", [
        "First release: daily collection of views, clones, referrers and stars with permanent history on GitHub Pages",
    ]),
]


def changelog_body(base):
    out = '<p class="lead">What changed in each release. Newest first.</p>'
    for v, d, items in CHANGELOG:
        out += f'<h2>{e(v)} <span class="mut" style="font-weight:400;font-size:14px"><time datetime="{d}">{d}</time></span></h2><ul>' + \
               "".join(f"<li>{e(i)}</li>" for i in items) + "</ul>"
    return out + f'<p class="note">Release notes are also published on <a href="https://github.com/musman550/github-traffic-analytics-dashboard/releases" rel="noopener">GitHub Releases</a>.</p>'


def changelog_md():
    out = "# Changelog\n\n"
    for v, d, items in CHANGELOG:
        out += f"## {v} - {d}\n" + "".join(f"- {i}\n" for i in items) + "\n"
    return out


# ---------------------------------------------------------------- status
def status_body(cfg, s, runs, base):
    h = s.get("health", {})
    rows = "".join(
        f'<tr><td>{e(r["d"][:16].replace("T", " "))} UTC</td><td>{"full" if r.get("full") else "incremental"}</td>'
        f'<td>{r["fetched"]}</td><td>{r["skipped"]}</td><td>{r["calls"]}</td><td>{r.get("left", "–")}</td><td>{r["s"]}s</td>'
        f'<td>{"partial" if r["partial"] else ("warnings" if r["errors"] else "ok")}</td></tr>' for r in runs[-20:][::-1])
    last = runs[-1] if runs else None
    ok = bool(last) and not last["partial"] and not last["errors"]
    state = "healthy" if ok else ("no run recorded yet" if not last else "needs attention")
    return (f'<p class="lead">Transparency about the data pipeline: when it last ran, how many API calls it used and whether anything went wrong.</p>'
            f'<h2>Current state</h2><ul><li>Last collection: {e((h.get("last_run") or "unknown")[:19].replace("T", " "))} UTC ({state})</li>'
            f'<li>Data through: {e(s["last_data_day"])}; page generated {e(s["generated"][:19].replace("T", " "))} UTC</li>'
            f'<li>Public repositories tracked: {s["totals"]["repos"]:,}</li></ul>'
            f'<h2>Recent runs</h2><div class="wrapx"><table><thead><tr><th>Started</th><th>Mode</th><th>Fetched</th><th>Skipped</th><th>API calls</th><th>Budget left</th><th>Duration</th><th>Result</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p class="note">The hourly GitHub API allowance is 5,000 requests per token. Runs stop safely when the remaining budget gets low.</p>'
            f'<h2>Monitoring</h2><p>A daily watchdog checks that the published data is fresh. A failed or partial run, a large traffic spike and every finished weekly report create an alert issue in the repository (and an optional Telegram message). '
            f'See the <a href="{base}methodology/">methodology</a> for how collection works and <a href="{base}changelog/">changelog</a> for releases.</p>')


# ---------------------------------------------------------------- repositories index
def repositories_body(cfg, s, base):
    rows = ""
    for r in s["repos"]:
        rows += (f'<tr><td style="white-space:normal"><a href="{e(r["url"])}" rel="noopener"><b>{e(r["name"])}</b></a>'
                 f'<div class="mut" style="font-size:12.5px">{e(r["desc"])}</div></td><td>{e(r["lang"] or "–")}</td><td>{r["stars"]}</td>'
                 f'<td>{r["v30"]:,}</td><td>{e(r["pushed"])}</td><td><a href="{base}#repo/{e(r["name"])}">Stats</a></td></tr>')
    t = s["totals"]
    return (f'<p class="lead">All {t["repos"]:,} public repositories with their GitHub description, language, stars and views in the last 30 days. '
            f'Use the <a href="{base}#repos">interactive table</a> to search, filter and compare.</p>'
            f'<div class="wrapx"><table><thead><tr><th>Repository</th><th>Language</th><th>Stars</th><th>Views 30d</th><th>Last push</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p class="note">Data through {e(s["last_data_day"])}. Private repositories are never included.</p>')


def repositories_itemlist(cfg, s, base):
    import json
    items = [{"@type": "ListItem", "position": i + 1, "url": r["url"], "name": r["name"]} for i, r in enumerate(s["repos"][:100])]
    return json.dumps({"@context": "https://schema.org", "@type": "ItemList", "name": "Public repositories by score",
                       "numberOfItems": len(s["repos"]), "itemListElement": items}, ensure_ascii=False)


# ---------------------------------------------------------------- optimizer transparency page
def _status_label(e):
    return {"applied": "applied", "kept": "kept after review", "reverted": "rolled back", "pending_pr": "README pull request open",
            "dry_run": "proposal (dry run)", "skipped": "no change needed"}.get(e.get("status"), e.get("status", ""))


def optimizer_body(cfg, state, ost, log, base):
    o = cfg["optimizer"]
    prov = "".join(
        f'<tr><td>{e(p["name"])}</td><td>{"open-weight" if p["open_weight"] else "closed (disabled)"}</td>'
        f'<td>{"yes" if p["configured"] else "no key"}</td><td>{p["ok"]}</td><td>{p["fail"] + p["bad"]}</td><td>{p["avg_ms"]} ms</td>'
        f'<td>{p["today"]}/{p["daily_cap"]}</td></tr>' for p in (state or {}).get("status", []))
    rows = ""
    for en in [x for x in log if x.get("mode") == "live"][::-1][:30]:
        ch = en.get("changes", {})
        what = []
        if "description" in ch:
            what.append("description")
        if "topics" in ch:
            add = len(ch["topics"]["after"]) - len(ch["topics"]["before"]) + len(ch["topics"].get("removed", []))
            what.append(f"+{max(add, 0)} topics" + (f", -{len(ch['topics']['removed'])} junk" if ch["topics"].get("removed") else ""))
        if en.get("readme"):
            what.append("README " + e(en["readme"].get("status", "")))
        imp = en.get("impact")
        rows += (f'<tr><td>{e(en["date"])}</td><td style="white-space:normal"><a href="https://github.com/{e(en["owner"])}/{e(en["repo"])}" rel="noopener">{e(en["repo"])}</a></td>'
                 f'<td>{e(en["class"])}</td><td>{e(", ".join(what) or "none")}</td><td>{e(en["source"].replace("ai:", ""))}</td>'
                 f'<td>{e(_status_label(en))}{f" ({imp['before']} to {imp['after']} views)" if imp else ""}</td></tr>')
    last = (ost or {}).get("last_run", "")[:16].replace("T", " ")
    return (f'<p class="lead">An automatic, auditable process improves GitHub metadata of the owner\'s public repositories. This page shows exactly how it works and what it has changed.</p>'
            f'<h2>What it does</h2><ul>'
            f'<li>Runs twice a week and picks up to {o["max_repos_per_run"]} public repositories, prioritising weak metadata, then traffic. A repository is revisited at most every {o["cooldown_days"]} days.</li>'
            f'<li><b>Descriptions</b> are replaced only when the current one is empty, too short or cut off.</li>'
            f'<li><b>Topics</b> are only added (up to {o["max_topics"]}) when the README supports them; only clear junk such as one-letter words is removed.</li>'
            f'<li><b>README</b> text changes happen only for hand-built tool repositories, as a pull request that edits one marked block. It is merged automatically after {o["auto_merge_days"]} days unless the owner closes it; closing it stops further proposals for {o["readme_declined_cooldown_days"]} days.</li>'
            f'<li>Never touched: private repositories, forks, archived repositories, the owner\'s profile repository and repositories that generate their own README.</li></ul>'
            f'<h2>How AI is used</h2><p>Text is drafted by open-weight models through free tiers of several providers with automatic fallback (see below). Only the public README, description, topics and file names of a repository are sent. Every answer must pass strict checks: topics must be grounded in the README, descriptions may not contain links or hype, FAQ answers may not contain numbers missing from the README, and a second model fact-checks the result. If no model is available or a check fails, a conservative rule-based fallback is used instead.</p>'
            f'<h2>Safety net</h2><p>Metadata changes are logged with before and after values. After {o["evaluate_after_days"]} days the dashboard compares views before and after; if views fell by more than {int(o["drop_threshold"] * 100)}% and the repository had at least {o["min_baseline_views"]} views, the change is rolled back automatically. With less traffic the change is kept because there is not enough data to judge.</p>'
            f'<h2>AI providers</h2><p class="note">Last run: {e(last or "none yet")} UTC.</p>'
            + (f'<div class="wrapx"><table><thead><tr><th>Provider</th><th>Models</th><th>Configured</th><th>Successful</th><th>Failed</th><th>Avg latency</th><th>Today</th></tr></thead><tbody>{prov}</tbody></table></div>' if prov else '<p>No run recorded yet.</p>')
            + f'<h2>Recent changes</h2>'
            + (f'<div class="wrapx"><table><thead><tr><th>Date</th><th>Repository</th><th>Type</th><th>Changed</th><th>Source</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>' if rows else '<p>No changes have been applied yet.</p>')
            + f'<p class="note">See also the <a href="{base}methodology/">methodology</a> and <a href="{base}status/">status page</a>.</p>')


# ---------------------------------------------------------------- citation block
def cite_block(cfg, s, prof, base):
    who = (prof or {}).get("name", "Publisher")
    return (f'<h2>Cite this dataset</h2><p><code>{e(who)}. GitHub Traffic Analytics Dashboard [data set]. {e(s["generated"][:10])}. '
            f'{e(base)}data/summary.json</code></p>')


# ---------------------------------------------------------------- social image for a weekly report
def report_og(w, s, outpath, site_name):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    if os.path.exists(outpath):
        return True
    os.makedirs(os.path.dirname(outpath), exist_ok=True)

    def font(sz, bold=False):
        for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else ""),):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
        return ImageFont.load_default()

    W, H = 1200, 630
    im = Image.new("RGB", (W, H), "#0b1220")
    d = ImageDraw.Draw(im)
    for i in range(H):
        d.line([(0, i), (W, i)], fill=(8, 18 + int(22 * i / H), 52 + int(40 * i / H)))
    end = w["start"] + dt.timedelta(days=6)
    d.text((70, 60), "WEEKLY GITHUB TRAFFIC REPORT", font=font(30, True), fill="#7fb0ff")
    d.text((70, 110), f"{fmt_d(w['start'])} to {fmt_d(end)}", font=font(54, True), fill="white")
    d.text((70, 215), f"{w['views']:,}", font=font(96, True), fill="white")
    d.text((70, 330), "views", font=font(34), fill="#b6c4dc")
    d.text((420, 215), f"{w['clones']:,}", font=font(96, True), fill="#7fe0a6")
    d.text((420, 330), "clones", font=font(34), fill="#b6c4dc")
    mx = max(w["dv"]) or 1
    for i, v in enumerate(w["dv"]):  # real daily views
        x = 760 + i * 58
        h = int(190 * v / mx)
        d.rounded_rectangle([x, 330 - h, x + 40, 330], radius=6, fill="#0b5fff")
        d.text((x + 8, 342), _d(w["days"][i]).strftime("%a")[:2], font=font(20), fill="#b6c4dc")
    d.text((70, 560), site_name, font=font(28), fill="#b6c4dc")
    im.save(outpath, optimize=True)
    return True
