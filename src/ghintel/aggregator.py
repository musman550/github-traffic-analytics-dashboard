"""Turn raw history into dashboard-ready summary.json (public repositories only)."""
import datetime as dt, math
from collections import Counter
from .insights import build_insights, seo_audit
from .store import load, save, today_utc

D = "docs/data"


def _d(s):
    return dt.date.fromisoformat(s)


def build_summary(cfg):
    series = load(f"{D}/series.json", {"repos": {}})["repos"]
    metas = {m["id"]: m for m in load(f"{D}/repos.json", [])}
    sources = load(f"{D}/sources.json", {"by_date": {}, "repos": {}})
    hist = load(f"{D}/totals_history.json", {})
    health = load(f"{D}/health.json", {})
    series = {k: v for k, v in series.items() if k in metas}  # public repos only

    today = dt.datetime.now(dt.timezone.utc).date()
    yesterday = today - dt.timedelta(days=1)
    all_days = {d for s in series.values() for k in ("views", "clones") for d in s[k]}
    complete = [d for d in all_days if _d(d) <= yesterday]
    last = max(complete) if complete else yesterday.isoformat()
    L = _d(last)
    first = min(all_days) if all_days else last

    def rng(n, off=0):
        return [(L - dt.timedelta(days=off + i)).isoformat() for i in range(n)]

    def ssum(s, kind, days, idx=0):
        return sum(s[kind].get(d, [0, 0])[idx] for d in days)

    d7, d30, p7 = rng(7), rng(30), rng(7, 7)

    agg = {}
    for s in series.values():
        for kind, off in (("views", 0), ("clones", 2)):
            for d, (c, u) in s[kind].items():
                a = agg.setdefault(d, [0, 0, 0, 0])
                a[off] += c
                a[off + 1] += u
    start = max(_d(first), L - dt.timedelta(days=399))
    daily, cur = [], start
    while cur <= L:
        k = cur.isoformat()
        daily.append([k] + agg.get(k, [0, 0, 0, 0]))
        cur += dt.timedelta(days=1)

    def bucket(keyf):
        out = {}
        for d in sorted(agg):
            if _d(d) > L:
                continue
            o = out.setdefault(keyf(_d(d)), [0, 0])
            o[0] += agg[d][0]
            o[1] += agg[d][2]
        return [[k, *v] for k, v in sorted(out.items())]

    weekly = bucket(lambda x: (x - dt.timedelta(days=x.weekday())).isoformat())
    monthly = bucket(lambda x: x.strftime("%Y-%m"))
    yearly = bucket(lambda x: x.strftime("%Y"))

    repos = []
    for rid, m in metas.items():
        s = series.get(rid, {"views": {}, "clones": {}})
        w = s.get("win", {})
        v7, v30 = ssum(s, "views", d7), ssum(s, "views", d30)
        c7, c30 = ssum(s, "clones", d7), ssum(s, "clones", d30)
        pv7 = ssum(s, "views", p7)
        vu = w.get("vu", 0)
        repos.append({
            "id": rid, "name": m["name"], "url": m["url"], "desc": m["desc"], "topics": m["topics"],
            "lang": m["lang"], "license": m["license"], "homepage": m["homepage"],
            "stars": m["stars"], "forks": m["forks"], "issues": m["issues"], "size": m["size"],
            "pushed": m["pushed"], "created": m["created"], "fork": m["fork"], "archived": m["archived"],
            "v1": s["views"].get(last, [0, 0])[0], "v7": v7, "v30": v30,
            "vall": sum(x[0] for x in s["views"].values()),
            "c7": c7, "c30": c30, "call": sum(x[0] for x in s["clones"].values()),
            "vu14": vu, "cu14": w.get("cu", 0),
            "pv7": pv7, "trend": round((v7 - pv7) * 100 / pv7) if pv7 else None,
            "score": round(v30 + 0.5 * c30 + 2 * vu + 3 * m["stars"] + 4 * m["forks"], 1),
            "spark": [s["views"].get(d, [0, 0])[0] for d in reversed(rng(14))],
            "audit": seo_audit(m, today),
        })

    elig = [r for r in repos if not r["fork"] and not r["archived"]]
    elig.sort(key=lambda r: (-r["score"], r["pushed"]))
    n = len(elig)
    k = max(1, math.ceil(n * 0.2)) if n else 0
    top_ids = {r["id"] for r in elig[:k]}
    low_ids = {r["id"] for r in elig[-k:]} if n > 2 * k else set()
    for r in repos:
        r["tier"] = "top" if r["id"] in top_ids else "low" if r["id"] in low_ids else "mid"
    repos.sort(key=lambda r: -r["score"])

    sd = sorted(sources["by_date"])
    latest = sources["by_date"][sd[-1]] if sd else {}
    src = sorted(([k2, v[0], v[1]] for k2, v in latest.items()), key=lambda x: -x[1])[:15]
    google = sum(v[0] for k2, v in latest.items() if "google" in k2.lower())
    src_trend = []
    for d in sd[-60:]:
        w = sources["by_date"][d]
        src_trend.append([d, sum(v[0] for v in w.values()),
                          sum(v[0] for k2, v in w.items() if "google" in k2.lower())])

    # portfolio breakdowns
    lang_repos, lang_views = Counter(), Counter()
    topic_repos, topic_views = Counter(), Counter()
    for r in repos:
        key = r["lang"] or "Unspecified"
        lang_repos[key] += 1
        lang_views[key] += r["v30"]
        for t in r["topics"]:
            topic_repos[t] += 1
            topic_views[t] += r["v30"]
    created = Counter(r["created"] for r in repos if r["created"])
    created_daily = [[(L - dt.timedelta(days=i)).isoformat(),
                      created.get((L - dt.timedelta(days=i)).isoformat(), 0)] for i in range(29, -1, -1)]
    wd = [0] * 7
    for d, v, *_ in daily[-90:]:
        wd[_d(d).weekday()] += v

    totals = {
        "repos": len(repos), "stars": sum(r["stars"] for r in repos), "forks": sum(r["forks"] for r in repos),
        "views_1d": sum(r["v1"] for r in repos), "views_7d": sum(r["v7"] for r in repos),
        "views_30d": sum(r["v30"] for r in repos), "views_all": sum(r["vall"] for r in repos),
        "views_prev7": sum(ssum(s, "views", p7) for s in series.values()),
        "clones_7d": sum(r["c7"] for r in repos), "clones_30d": sum(r["c30"] for r in repos),
        "clones_all": sum(r["call"] for r in repos), "vu14": sum(r["vu14"] for r in repos),
        "google_14d": google, "referrals_14d": sum(x[1] for x in src),
        "audit_avg": round(sum(r["audit"]["score"] for r in repos) / len(repos)) if repos else 0,
        "active_30d": sum(1 for r in repos if r["v30"] > 0),
    }
    summary = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "last_data_day": last, "first_data_day": first, "site_url": cfg["site_url"],
        "totals": totals, "daily": daily, "weekly": weekly, "monthly": monthly, "yearly": yearly,
        "weekday": wd, "repos": repos, "sources": src, "sources_trend": src_trend,
        "history": [[d] + hist[d] for d in sorted(hist)][-400:],
        "languages": [[k2, lang_repos[k2], lang_views[k2]] for k2, _ in lang_repos.most_common(12)],
        "topics": [[k2, topic_repos[k2], topic_views[k2]] for k2, _ in topic_repos.most_common(30)],
        "created_daily": created_daily, "repo_sources": sources.get("repos", {}), "health": health,
        "insights": build_insights(totals, repos, daily, src, last, today),
    }
    save(f"{D}/summary.json", summary)
    return summary
