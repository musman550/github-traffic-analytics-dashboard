"""Pre-publish audit: fails the workflow if the generated site is malformed.
Checks: strict HTML parse, duplicate ids, internal links, JSON-LD, title/description length,
sitemap targets, no private-repo markers in published data."""
import html5lib, json, os, re, sys
from html.parser import HTMLParser

ROOT = sys.argv[1] if len(sys.argv) > 1 else "docs"
BASE = json.load(open("config/config.json"))["site_url"]
errs = []


class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.ids = []; s.links = []; s.noalt = 0; s.h1 = 0
    def handle_starttag(s, t, a):
        a = dict(a)
        if "id" in a: s.ids.append(a["id"])
        if t == "a" and a.get("href"): s.links.append(a["href"])
        if t == "img" and "alt" not in a: s.noalt += 1
        if t == "h1": s.h1 += 1


def target(link):
    if not link.startswith(BASE): return True
    path = link[len(BASE):].split("#")[0].split("?")[0]
    t = os.path.join(ROOT, path)
    if os.path.isdir(t) or path == "" or path.endswith("/"): t = os.path.join(t, "index.html")
    return os.path.exists(t)


pages = [os.path.join(d, f) for d, _, fs in os.walk(ROOT) for f in fs if f.endswith(".html")]
for p in pages:
    rel = os.path.relpath(p, ROOT)
    txt = open(p, encoding="utf-8").read()
    try:
        html5lib.HTMLParser(strict=True).parse(txt)
    except Exception as e:
        errs.append(f"{rel}: HTML parse error {str(e)[:100]}")
    q = P(); q.feed(txt)
    if q.h1 != 1: errs.append(f"{rel}: {q.h1} h1 tags")
    for i in {i for i in q.ids if q.ids.count(i) > 1}: errs.append(f"{rel}: duplicate id {i}")
    if q.noalt: errs.append(f"{rel}: {q.noalt} images without alt")
    for l in q.links:
        if not target(l): errs.append(f"{rel}: broken internal link {l}")
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', txt, re.S):
        try: json.loads(m.group(1))
        except Exception as e: errs.append(f"{rel}: invalid JSON-LD ({e})")
    t = re.search(r"<title>(.*?)</title>", txt); d = re.search(r'name="description" content="(.*?)"', txt)
    if not t or len(t.group(1)) > 80: errs.append(f"{rel}: title missing or over 80 chars")
    if rel != "404.html" and (not d or not 50 <= len(d.group(1)) <= 165): errs.append(f"{rel}: description length {len(d.group(1)) if d else 0}")
sm = open(os.path.join(ROOT, "sitemap.xml")).read()
for u in re.findall(r"<loc>(.*?)</loc>", sm):
    if not target(u): errs.append(f"sitemap: missing target {u}")
for f in ("summary.json", "repos.json", "series.json", "sources.json"):
    raw = open(os.path.join(ROOT, "data", f)).read()
    if re.search(r'private-[0-9a-f]{6}"', raw) or '"private":true' in raw.replace(" ", ""):
        errs.append(f"data/{f}: private-repo marker found")
s = json.load(open(os.path.join(ROOT, "data", "summary.json")))
if not s["repos"] or s["totals"]["repos"] != len(s["repos"]): errs.append("summary: repo count mismatch")
print(f"audited {len(pages)} pages, {len(errs)} problem(s)")
for e in errs: print(" -", e)
sys.exit(1 if errs else 0)
