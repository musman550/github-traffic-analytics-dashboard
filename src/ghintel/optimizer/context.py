"""Collect the facts the optimizer is allowed to use: only the repository's own public content."""
from .generate import clean_readme


def gather(gh, meta, ocfg):
    full = f"{meta['owner']}/{meta['name']}"
    readme = gh.text(f"/repos/{full}/readme") or ""
    files, _ = gh.get(f"/repos/{full}/contents/")
    names = [f["name"] for f in files] if isinstance(files, list) else []
    return {"name": meta["name"], "full": full, "desc": meta.get("desc", ""), "topics": list(meta.get("topics", [])),
            "lang": meta.get("lang"), "license": meta.get("license"), "homepage": meta.get("homepage", ""),
            "branch": meta.get("branch") or "main", "files": names, "has_readme": bool(readme),
            "readme_raw": readme, "readme": clean_readme(readme, ocfg["block_start"], ocfg["block_end"])}


def rank_topics(gh, topics, stats, today, ttl_days=30, pause=2.2):
    """Keep topics that other repositories actually use (discoverability) and order them by usefulness."""
    import time
    ranked = []
    for t in topics:
        c = stats.get(t)
        if not c or (today - __import__("datetime").date.fromisoformat(c["d"])).days > ttl_days:
            data, _ = gh.get("/search/repositories", {"q": f"topic:{t}", "per_page": 1})
            time.sleep(pause)
            if data is None:
                ranked.append((t, None))
                continue
            c = {"n": data.get("total_count", 0), "d": today.isoformat()}
            stats[t] = c
        ranked.append((t, c["n"]))
    keep = [(t, n) for t, n in ranked if n is None or n >= 1]
    keep.sort(key=lambda x: (0 if x[1] is None else (0 if 50 <= x[1] <= 200000 else 1), -(x[1] or 0)))
    return [t for t, _ in keep]
