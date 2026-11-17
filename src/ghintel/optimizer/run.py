"""Weekly optimizer: pick repositories, propose safe metadata, apply (or dry-run), log everything."""
import datetime as dt, os
from ..ai.router import Router
from ..github_client import GH, RateGuard
from ..store import load, save, today_utc
from . import apply as A, context as X, evaluate as E, generate as G, select as S

D = "docs/data"


def _flag(name, default=False):
    v = os.environ.get(name)
    return default if v is None or v == "" else v.lower() in ("1", "true", "yes")


def run(cfg, dry=None, limit=None, only=None, rules_only=None):
    o = cfg["optimizer"]
    if not o.get("enabled", True):
        print("optimizer disabled in config")
        return {}
    dry = _flag("OPT_DRY", False) if dry is None else dry
    rules_only = _flag("OPT_RULES_ONLY", False) if rules_only is None else rules_only
    limit = limit or int(os.environ.get("OPT_LIMIT") or 0) or None
    only = only or os.environ.get("OPT_REPO") or None
    today = today_utc()
    summary = load(f"{D}/summary.json")
    metas = {m["id"]: m for m in load(f"{D}/repos.json", [])}
    prof = load(f"{D}/profile.json", {}) or {}
    log = load(f"{D}/optimizer_log.json", [])
    series = load(f"{D}/series.json", {"repos": {}})["repos"]
    state = load(f"{D}/ai_state.json", {})
    cache = load(f"{D}/ai_cache.json", {})
    topic_stats = load(f"{D}/topic_stats.json", {})
    owner = prof.get("login") or next((m["url"].split("/")[3] for m in metas.values()), "")
    base = cfg["site_url"]
    website = next((l["url"] for l in prof.get("links", []) if l["kind"] == "website"), "")

    gh = GH(min_remaining=cfg["min_rate_remaining"], sleep=0.2)
    router = Router(cfg, state, cache)
    notes_run, counts = [], {"checked": 0, "applied": 0, "prs": 0, "skipped": 0, "ai": 0, "rules": 0}
    try:
        if not dry:
            notes_run += E.refresh_prs(gh, log, o, today)
            notes_run += E.evaluate_changes(gh, log, series, o, today)
        picks = S.select(cfg, summary["repos"], log, today, limit, only)
        print(f"optimizer: mode={'DRY-RUN' if dry else 'LIVE'} candidates={len(picks)} "
              f"providers={[p['name'] for p in router.ordered()] or 'none (rules only)'}")
        for prio, name, cls, r in picks:
            m = dict(metas.get(name, {}))
            m["owner"] = owner
            try:
                ctx = X.gather(gh, m, o)
                full = cls == "product" or o.get("generated_readme")
                prop, notes = G.propose(router, ctx, full, o.get("use_judge", True), rules_only)
                counts["ai" if prop["source"].startswith("ai:") else "rules"] += 1
                if cls == "generated":  # near-identical generated repos: clean up, never mass-add topics
                    prop["topics"] = prop["topics"][:o.get("generated_max_new_topics", 3)] if prop["source"].startswith("ai:") else []
                ranked = X.rank_topics(gh, [t for t in prop.get("topics", []) if t not in ctx["topics"]], topic_stats, today)
                ch = A.metadata_changes(ctx, prop, ranked, o)
                entry = {"id": f"{today}:{name}", "repo": name, "owner": owner, "date": today.isoformat(), "class": cls,
                         "mode": "dry" if dry else "live", "source": prop["source"], "priority": prio, "notes": notes,
                         "changes": ch, "readme": None, "baseline": {"views_14d": E.views_between(series, name, today - dt.timedelta(days=15), today - dt.timedelta(days=2))}}
                if prop.get("judge"):
                    entry["judge"] = prop["judge"]
                # README block (product repos only, via pull request)
                if full and ctx["has_readme"] and not S.readme_declined(log, name, today, o["readme_declined_cooldown_days"]) and not S.has_open_pr(log, name):
                    allt = A.merge_topics(ctx["topics"], ranked, o["max_topics"])
                    rel = A.related(summary["repos"], ctx, o, S.classify)
                    block = A.build_block(ctx, prop, allt, rel, website, o, base)
                    new = A.upsert_block(ctx["readme_raw"], block, o["block_start"], o["block_end"])
                    if block and new != ctx["readme_raw"]:
                        entry["readme"] = {"repo": ctx["full"], "status": "proposed", "preview": block[:1800]}
                        if not dry:
                            pr = A.open_readme_pr(gh, ctx, new, o, today, f"Automatic proposal ({prop['source']}) based only on this repository's own content.")
                            if pr:
                                entry["readme"] = pr
                                counts["prs"] += 1
                            else:
                                entry["readme"]["status"] = "failed"
                if dry:
                    entry["status"] = "dry_run"
                else:
                    if "description" in ch:
                        code, _ = gh.send("PATCH", f"/repos/{ctx['full']}", {"description": ch["description"]["after"]})
                        if code != 200:
                            del ch["description"]
                    if "topics" in ch:
                        code, _ = gh.send("PUT", f"/repos/{ctx['full']}/topics", {"names": ch["topics"]["after"]})
                        if code != 200:
                            del ch["topics"]
                    if ch:
                        entry["status"] = "applied"
                        counts["applied"] += 1
                    elif entry["readme"] and entry["readme"].get("status") == "pending":
                        entry["status"] = "pending_pr"
                    else:
                        entry["status"] = "skipped"
                        counts["skipped"] += 1
                counts["checked"] += 1
                log.append(entry)
                print(f"  {name} [{cls}] {entry['status']} via {prop['source']}: {', '.join(ch) or 'no metadata change'}"
                      + (f"; README {entry['readme']['status']}" if entry["readme"] else ""))
            except RateGuard:
                notes_run.append("rate guard: stopped early")
                break
            except Exception as e:
                notes_run.append(f"{name}: {type(e).__name__}: {e}")
                print(f"  {name}: error {type(e).__name__}: {e}")
    finally:
        router.trim_cache()
        state["status"] = router.status()
        state["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        save(f"{D}/ai_state.json", state, pretty=True)
        save(f"{D}/ai_cache.json", cache)
        save(f"{D}/topic_stats.json", topic_stats)
        save(f"{D}/optimizer_log.json", log[-600:])
        save(f"{D}/optimizer_state.json", {
            "last_run": state["updated"], "mode": "dry" if dry else "live", "counts": counts, "notes": notes_run[:10],
            "api_calls": gh.calls, "ai_calls": router.calls, "enabled": True,
            "providers_configured": [p["name"] for p in router.providers if router._key(p)]}, pretty=True)
    print(f"optimizer done: {counts} ai_calls={router.calls} api_calls={gh.calls} notes={notes_run[:3]}")
    return counts
