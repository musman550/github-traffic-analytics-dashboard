"""Tell IndexNow-enabled search engines (Bing, Yandex, Seznam, Naver...) that pages changed.
Google does not use IndexNow. Best effort: never fails the workflow."""
import json, sys, urllib.request
sys.path.insert(0, "src")
from ghintel.site import indexnow_key

cfg = json.load(open("config/config.json"))
base = cfg["site_url"]
key = indexnow_key(cfg)
urls = json.load(open("docs/indexnow-urls.json"))
host = base.split("//", 1)[1].split("/", 1)[0]
body = json.dumps({"host": host, "key": key, "keyLocation": f"{base}{key}.txt", "urlList": urls[:200]}).encode()
req = urllib.request.Request("https://api.indexnow.org/IndexNow", data=body, method="POST",
                             headers={"Content-Type": "application/json; charset=utf-8"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print("IndexNow status", r.status, "for", len(urls), "urls")
except Exception as e:
    print("IndexNow skipped:", e)
