"""Which repositories get optimized, and in what order."""
import datetime as dt, math


def classify(name, ocfg):
    return "generated" if any(name.startswith(p) for p in ocfg.get("generated_prefixes", [])) else "product"


def live_entries(log, repo=None):
    return [e for e in log if e.get("mode") == "live" and (repo is None or e["repo"] == repo)]


def last_touch(log, repo):
    """(date, source) of the latest live touch."""
    es = sorted(live_entries(log, repo), key=lambda e: e["date"])
    return (es[-1]["date"], es[-1].get("source", "")) if es else (None, "")


def readme_declined(log, repo, today, days):
    for e in live_entries(log, repo):
        r = e.get("readme") or {}
        if r.get("status") == "declined":
            if (today - dt.date.fromisoformat(r.get("closed", e["date"]))).days < days:
                return True
    return False


def has_open_pr(log, repo):
    return any((e.get("readme") or {}).get("status") == "pending" for e in live_entries(log, repo))


def priority(r, cls):
    need = 100 - r["audit"]["score"]
    tier = 30 if r["tier"] == "top" else 10 if r["tier"] == "low" else 0
    return round(need * 0.6 + tier + min(20, math.log1p(r["v30"]) * 4) + (15 if cls == "product" else 0), 1)


def select(cfg, repos, log, today, limit=None, only=None):
    o = cfg["optimizer"]
    limit = limit or o["max_repos_per_run"]
    out = []
    for r in repos:
        n = r["name"]
        if only and n != only:
            continue
        if n in o["exclude"] or r["fork"] or r["archived"]:
            continue
        lt, src = last_touch(log, n)
        wait = o.get("rules_cooldown_days", 3) if src == "rules" else o["cooldown_days"]  # let AI redo rule-only work soon
        if lt and not only and (today - dt.date.fromisoformat(lt)).days < wait:
            continue
        cls = classify(n, o)
        out.append((priority(r, cls), n, cls, r))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out[:limit]
