"""Close the loop: follow README pull requests, auto-merge quiet ones, and roll back metadata
changes that were followed by a clear traffic drop."""
import datetime as dt


def views_between(series, repo, start, end):
    s = series.get(repo, {}).get("views", {})
    total, d = 0, start
    while d <= end:
        total += s.get(d.isoformat(), [0, 0])[0]
        d += dt.timedelta(days=1)
    return total


def refresh_prs(gw, log, ocfg, today):
    notes = []
    for e in log:
        r = e.get("readme")
        if e.get("mode") != "live" or not r or r.get("status") != "pending":
            continue
        data, _ = gw.get(f"/repos/{r['repo']}/pulls/{r['number']}")
        if not data:
            continue
        if data.get("merged"):
            r["status"], r["closed"] = "merged", today.isoformat()
        elif data.get("state") == "closed":
            r["status"], r["closed"] = "declined", today.isoformat()
        else:
            age = (today - dt.date.fromisoformat(r["opened"])).days
            days = ocfg.get("auto_merge_days", 0)
            if days and age >= days and data.get("mergeable") is True:
                code, _ = gw.send("PUT", f"/repos/{r['repo']}/pulls/{r['number']}/merge", {"merge_method": "squash"})
                if code == 200:
                    r["status"], r["closed"] = "merged", today.isoformat()
                    notes.append(f"auto-merged {r['repo']}#{r['number']}")
    return notes


def evaluate_changes(gw, log, series, ocfg, today):
    notes = []
    for e in log:
        if e.get("mode") != "live" or e.get("status") != "applied" or not ({"description", "topics"} & set(e.get("changes", {}))):
            continue
        d = dt.date.fromisoformat(e["date"])
        n = ocfg["evaluate_after_days"]
        if (today - d).days < n + 2:  # GitHub finalises traffic days after 24-48 h
            continue
        before = views_between(series, e["repo"], d - dt.timedelta(days=n), d - dt.timedelta(days=1))
        after = views_between(series, e["repo"], d + dt.timedelta(days=1), d + dt.timedelta(days=n))
        e["impact"] = {"before": before, "after": after, "days": n}
        if before >= ocfg["min_baseline_views"] and after < before * (1 - ocfg["drop_threshold"]):
            ch = e["changes"]
            full = f"{e['owner']}/{e['repo']}"
            if "description" in ch:
                gw.send("PATCH", f"/repos/{full}", {"description": ch["description"]["before"]})
            if "topics" in ch:
                gw.send("PUT", f"/repos/{full}/topics", {"names": ch["topics"]["before"]})
            e["status"] = "reverted"
            notes.append(f"reverted {e['repo']} (views {before} -> {after})")
        else:
            e["status"] = "kept"
            e["impact"]["note"] = "insufficient traffic to judge" if before < ocfg["min_baseline_views"] else "no clear drop"
    return notes

