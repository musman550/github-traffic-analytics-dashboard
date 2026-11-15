"""Long-form, crawlable pages: weekly reports, guides, extended FAQ and data documentation.
Every figure is computed from stored data; guides contain verified, documented facts only."""
import datetime as dt, html
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
<h2>Notes</h2><ul><li>Only public repositories are included.</li><li>Clones include automation.</li><li>See the <a href="{base}methodology/">methodology</a> for definitions and limits.</li></ul>"""
