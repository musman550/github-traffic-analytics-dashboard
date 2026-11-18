"""Live self-test of every configured provider: lists models and sends a tiny request to the first few.
Writes docs/data/ai_probe.json (statuses, latency, short response snippets; no secrets)."""
import datetime as dt, json
from .router import Router
from ..store import save


def snippet(data, n=260):
    return (data if isinstance(data, str) else json.dumps(data, ensure_ascii=False))[:n]


def probe(cfg):
    r = Router(cfg, {}, {})
    out = {"date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "providers": []}
    for p in r.providers:
        e = {"name": p["name"], "open_weight": p.get("open", True)}
        if not r._key(p):
            e["skipped"] = "no key configured"
        elif not (p.get("open", True) or r.allow_closed):
            e["skipped"] = "closed models disabled"
        else:
            if p.get("discover"):
                try:
                    e["discovered"] = r._discover(p, p["discover"])[:6]
                except Exception as ex:
                    e["discovered_error"] = f"{type(ex).__name__}: {ex}"
                e["discover_error"] = r.state.get("discover_error", {}).get(p["name"], "")
            e["tests"] = []
            for model in r.models_for(p)[:3]:
                for json_mode in (True, False):
                    st, h, data, ms = r._call(p, model, "You reply with JSON only.", 'Return exactly {"ok": true}', 60, 0, json_mode)
                    text = ""
                    try:
                        text = data["choices"][0]["message"]["content"] or ""
                    except Exception:
                        pass
                    e["tests"].append({"model": model, "json_mode": json_mode, "status": st, "ms": ms, "content": text[:120],
                                       "raw": "" if text else snippet(data)})
                    if st == 200 and text:
                        break
        out["providers"].append(e)
    save("docs/data/ai_probe.json", out, pretty=True)
    ok = [p["name"] for p in out["providers"] if any(t["status"] == 200 and t["content"] for t in p.get("tests", []))]
    print("probe: working providers:", ok or "none")
    return out
