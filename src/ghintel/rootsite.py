"""Host-root files for https://<login>.github.io/ : robots.txt, llms.txt, sitemap index, security.txt and a small hub page.

Crawlers read robots.txt only from the host root, and a project site (/repo-name/) cannot provide it. This module
generates those files from the same collected data and publishes them to the user-site repository
<login>/<login>.github.io (created on first run). Files are written only when their content changed."""
import base64, datetime as dt, html, json, os
from .site import AI_BOTS
from .store import load

e = html.escape


def _classify(name, ocfg):
    return "generated" if any(name.startswith(p) for p in ocfg.get("generated_prefixes", [])) else "product"


def build_files(cfg, summary, prof, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    login = (prof or {}).get("login", "")
    root = f"https://{login}.github.io/"
    dash = cfg["site_url"]
    name = (prof or {}).get("name", login)
    o = cfg.get("optimizer", {})
    tools = [r for r in summary["repos"] if not r["fork"] and not r["archived"] and _classify(r["name"], o) == "product"
             and r["name"] not in o.get("exclude", []) and r["name"] != cfg["repo_full_name"].split("/")[1]][:12]
    links = (prof or {}).get("links", [])
    bots = "".join(f"User-agent: {b}\nAllow: /\n\n" for b in AI_BOTS)
    files = {}
    files["robots.txt"] = (f"User-agent: *\nAllow: /\n\n{bots}Sitemap: {root}sitemap.xml\nSitemap: {dash}sitemap.xml\n")
    files["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                            f"<sitemap><loc>{root}sitemap-root.xml</loc><lastmod>{today}</lastmod></sitemap>"
                            f"<sitemap><loc>{dash}sitemap.xml</loc><lastmod>{today}</lastmod></sitemap></sitemapindex>\n")
    files["sitemap-root.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                 f"<url><loc>{root}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq></url></urlset>\n")
    tool_lines = "\n".join(f"- [{r['name']}]({r['url']})" + (f": {r['desc']}" if r["desc"] and 30 <= len(r["desc"]) <= 200 else "") for r in tools)
    link_lines = "\n".join(f"- [{l['label']}]({l['url']})" for l in links)
    files["llms.txt"] = (f"# {name}\n\n> {(prof or {}).get('tagline') or 'Open-source AI automation tools and dashboards.'}\n\n"
                         f"## Main projects\n- [GitHub Traffic Analytics Dashboard]({dash}): permanent history of GitHub views, clones and referrers; "
                         f"[llms.txt]({dash}llms.txt), [open data]({dash}data/)\n{tool_lines}\n\n## Links\n- [GitHub profile]({(prof or {}).get('url', '')})\n{link_lines}\n")
    files[".well-known/security.txt"] = (f"Contact: https://github.com/{cfg['repo_full_name']}/security/advisories/new\n"
                                         f"Expires: {(dt.date.fromisoformat(today) + dt.timedelta(days=365)).isoformat()}T00:00:00.000Z\n"
                                         f"Preferred-Languages: en\nCanonical: {root}.well-known/security.txt\n")
    items = "".join(f'<li><a href="{e(r["url"])}" rel="noopener"><b>{e(r["name"])}</b></a>'
                    + (f'<br><span>{e(r["desc"])}</span>' if r["desc"] and 30 <= len(r["desc"]) <= 200 else "") + "</li>" for r in tools)
    socials = "".join(f'<li><a href="{e(l["url"])}" rel="me noopener">{e(l["label"])}</a></li>' for l in links)
    ld = json.dumps({"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "@id": root + "#website", "url": root, "name": name, "inLanguage": "en"},
        {"@type": "Organization", "@id": root + "#org", "name": name, "url": root, "sameAs": [l["url"] for l in links] + ([prof["url"]] if prof else []),
         **({"logo": prof["avatar"]} if prof and prof.get("avatar") else {})},
        {"@type": "WebPage", "@id": root + "#webpage", "url": root, "name": f"{name}: open-source AI tools and dashboards", "isPartOf": {"@id": root + "#website"}, "dateModified": today}]},
        ensure_ascii=False)
    desc = f"{name}: open-source AI automation tools and a free GitHub traffic analytics dashboard."
    files["index.html"] = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(name)}: open-source AI tools and dashboards</title>
<meta name="description" content="{e(desc[:155])}">
<link rel="canonical" href="{root}">
<link rel="sitemap" type="application/xml" href="{root}sitemap.xml">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta property="og:type" content="website"><meta property="og:title" content="{e(name)}"><meta property="og:description" content="{e(desc[:155])}"><meta property="og:url" content="{root}">
<meta property="og:image" content="{dash}assets/og-image.png">
<script type="application/ld+json">{ld}</script>
<style>:root{{color-scheme:light dark}}body{{font:16px/1.6 system-ui,sans-serif;max-width:760px;margin:0 auto;padding:24px}}a{{color:#0b5fff}}h1{{margin-bottom:4px}}.mut,span{{color:#667}}li{{margin:8px 0}}footer{{margin-top:32px;font-size:13px;color:#667}}</style></head>
<body><main><h1>{e(name)}</h1>
<p class="mut">{e((prof or {}).get("tagline") or "Open-source AI automation tools.")}</p>
<h2>Featured</h2>
<ul><li><a href="{dash}"><b>GitHub Traffic Analytics Dashboard</b></a><br><span>Free, open-source history of views, clones, referrers and stars for public repositories, with weekly reports and open data.</span></li></ul>
<h2>Tools and projects</h2><ul>{items}</ul>
<h2>Find us</h2><ul><li><a href="{e((prof or {}).get("url", ""))}" rel="me noopener">GitHub</a></li>{socials}</ul>
<p><a href="{root}llms.txt">llms.txt</a> &middot; <a href="{root}sitemap.xml">sitemap</a> &middot; <a href="{dash}data/">open data</a></p></main>
<footer>&copy; {today[:4]} {e(name)}. Not affiliated with GitHub, Inc. Updated {today}.</footer></body></html>
"""
    files["404.html"] = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Not found</title><meta name="robots" content="noindex"></head>'
                         f'<body><h1>Page not found</h1><p><a href="{root}">Home</a> &middot; <a href="{dash}">Traffic Analytics Dashboard</a></p></body></html>\n')
    files[".nojekyll"] = ""
    return files


def _api(token, method, path, body=None):
    import urllib.request, urllib.error
    req = urllib.request.Request("https://api.github.com" + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as ex:
        return ex.code, (json.loads(ex.read() or b"null") if ex.headers.get("content-type", "").startswith("application/json") else None)


def publish(cfg, files, login, token):
    repo = f"{login}/{login}.github.io"
    st, _ = _api(token, "GET", f"/repos/{repo}")
    if st == 404:
        st, _ = _api(token, "POST", "/user/repos", {"name": f"{login}.github.io", "description": "Host-root files (robots.txt, llms.txt, sitemap) for my GitHub Pages sites",
                                                      "private": False, "has_issues": False, "has_wiki": False, "has_projects": False})
        if st not in (200, 201):
            return {"error": f"could not create {repo} ({st})"}
    changed = []
    for path, text in files.items():
        st, cur = _api(token, "GET", f"/repos/{repo}/contents/{path}")
        sha = cur.get("sha") if st == 200 and isinstance(cur, dict) else None
        if sha and base64.b64decode(cur["content"]).decode("utf-8") == text:
            continue
        body = {"message": f"update {path}", "content": base64.b64encode(text.encode()).decode(), "branch": "main"}
        if sha:
            body["sha"] = sha
        st, res = _api(token, "PUT", f"/repos/{repo}/contents/{path}", body)
        if st in (200, 201):
            changed.append(path)
    _api(token, "POST", f"/repos/{repo}/pages", {"source": {"branch": "main", "path": "/"}})  # no-op if already enabled
    return {"repo": repo, "changed": changed}


def run(cfg):
    s, prof = load("docs/data/summary.json"), load("docs/data/profile.json")
    if not (s and prof and prof.get("login")):
        print("rootsite: missing data")
        return
    files = build_files(cfg, s, prof)
    os.makedirs("docs/_rootsite", exist_ok=True)  # local copy for inspection only (not served)
    token = os.environ.get("GH_PAT")
    if token and cfg.get("root_site", True):
        print("rootsite:", publish(cfg, files, prof["login"], token))
    else:
        print("rootsite: generated", len(files), "files (not published: no token or disabled)")
