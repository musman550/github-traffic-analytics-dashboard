"""Collect GitHub traffic for every PUBLIC owned repo and merge it into permanent history.

Rate-limit strategy (no limit hits):
  * GitHub returns a rolling 14-day window per call, so a repo does not need to be fetched
    every day to lose nothing. Active repos are fetched daily, idle ones every 3 days,
    dormant ones weekly (all < 14 days), staggered by a stable hash so load is even.
  * Sequential calls with a small delay, retry/backoff, and a hard stop when the remaining
    hourly budget drops below a safety floor (the run saves what it has and exits cleanly).
Private repositories are never read, stored or published.
"""
import datetime as dt, hashlib, os, re, time
from .github_client import GH, RateGuard
from .profile import fetch_profile
from .store import load, save, today_utc

D = "docs/data"


def _h(name):
    return int(hashlib.md5(name.encode()).hexdigest(), 16)


def cadence_for(st, today, cfg):
    c = cfg["cadence"]
    act = st.get("a")
    if act and (today - dt.date.fromisoformat(act)).days < 14:
        return c["active_days"]
    ref = dt.date.fromisoformat(act or st.get("s", today.isoformat()))
    if (today - ref).days >= c["dormant_after_idle_days"]:
        return c["dormant_days"]
    return c["idle_days"]


def is_due(rid, today, state, cfg, force=False):
    st = state.get(rid)
    if force or not st or "f" not in st:
        return True
    return (today - dt.date.fromisoformat(st["f"])).days >= cadence_for(st, today, cfg)


def merge_days(dst, entries):
    """Upsert days into a sparse map; zero days are not stored."""
    for e in entries or []:
        day = e["timestamp"][:10]
        if e["count"] or e["uniques"]:
            dst[day] = [e["count"], e["uniques"]]
        else:
            dst.pop(day, None)


def collect(cfg):
    t0 = time.time()
    gh = GH(min_remaining=cfg["min_rate_remaining"], sleep=cfg["sleep_between_calls"])
    now = dt.datetime.now(dt.timezone.utc)
    today = today_utc()
    force = os.environ.get("FORCE_FULL", "").lower() in ("1", "true", "yes")
    limit = int(os.environ.get("GHINTEL_LIMIT", "0") or 0)

    series = load(f"{D}/series.json", {"repos": {}})
    sources = load(f"{D}/sources.json", {"by_date": {}, "repos": {}})
    hist = load(f"{D}/totals_history.json", {})
    state = load(f"{D}/state.json", {})
    errors, partial, fetched, skipped = [], False, 0, 0

    # privacy migration: drop anything that was ever stored for private repos
    anon = re.compile(r"^private-[0-9a-f]{6}$")  # ids once used for anonymized private repos
    for k in [k for k in series["repos"] if anon.match(k)]:
        del series["repos"][k]
    for k in [k for k in state if anon.match(k)]:
        del state[k]
    for s in series["repos"].values():  # keep storage sparse: zero days carry no information
        for kind in ("views", "clones"):
            for day in [d for d, v in s[kind].items() if not v[0] and not v[1]]:
                del s[kind][day]

    # activity for scheduling = last day with human-visible views. Clones are excluded on purpose:
    # almost every repository is cloned by automation daily, which would make all repos "active".
    for name, s in series["repos"].items():
        st = state.setdefault(name, {"s": today.isoformat()})
        if s["views"]:
            st["a"] = max(s["views"])
        else:
            st.pop("a", None)

    raw = gh.paginate("/user/repos", {"per_page": 100, "affiliation": "owner", "sort": "full_name"})
    public = [r for r in raw if not r["private"]]
    login = public[0]["owner"]["login"] if public else None

    metas = []
    for r in public:
        lic = (r.get("license") or {}).get("spdx_id")
        metas.append({
            "id": r["name"], "name": r["name"], "url": r["html_url"], "desc": r.get("description") or "",
            "topics": r.get("topics", []), "lang": r.get("language"), "license": lic if lic != "NOASSERTION" else None,
            "homepage": r.get("homepage") or "", "stars": r["stargazers_count"], "forks": r["forks_count"],
            "watchers": r["watchers_count"], "issues": r["open_issues_count"],
            "pushed": (r.get("pushed_at") or "")[:10], "created": (r.get("created_at") or "")[:10],
            "size": r.get("size", 0), "fork": r["fork"], "archived": r["archived"],
            "pages": bool(r.get("has_pages")), "branch": r.get("default_branch"),
        })

    agg_ref = {}
    per_repo = dict(sources.get("repos", {}))
    todo = 0
    for r in public:
        if partial or (limit and todo >= limit):
            break
        name = r["name"]
        if name in cfg["exclude"]:
            continue
        if (r["fork"] and not cfg["include_forks"]) or (r["archived"] and not cfg["include_archived"]):
            continue
        if not is_due(name, today, state, cfg, force):
            skipped += 1
            continue
        todo += 1
        try:
            views, _ = gh.get(f"/repos/{r['full_name']}/traffic/views")
            clones, _ = gh.get(f"/repos/{r['full_name']}/traffic/clones")
            if views is None or clones is None:
                errors.append(f"{name}: no traffic access")
                continue
            s = series["repos"].setdefault(name, {"views": {}, "clones": {}})
            merge_days(s["views"], views.get("views"))
            merge_days(s["clones"], clones.get("clones"))
            s["win"] = {"d": today.isoformat(), "vc": views["count"], "vu": views["uniques"],
                        "cc": clones["count"], "cu": clones["uniques"]}
            st = state.setdefault(name, {"s": today.isoformat()})
            if views["count"]:  # referrers and paths only describe views
                st["a"] = max(max(s["views"]), st.get("a", ""))
                refs, _ = gh.get(f"/repos/{r['full_name']}/traffic/popular/referrers")
                paths, _ = gh.get(f"/repos/{r['full_name']}/traffic/popular/paths")
                for x in refs or []:
                    a = agg_ref.setdefault(x["referrer"], [0, 0])
                    a[0] += x["count"]; a[1] += x["uniques"]
                per_repo[name] = {
                    "ref": [[x["referrer"], x["count"], x["uniques"]] for x in (refs or [])[:5]],
                    "paths": [[x["path"], x["title"], x["count"], x["uniques"]] for x in (paths or [])[:5]],
                }
            else:
                per_repo.pop(name, None)
            # spread first-time fetches over the cadence window so idle repos do not all fall due on the
            # same day; afterwards the period stays exactly `cad` days
            cad = cadence_for(st, today, cfg)
            first = "f" not in st
            st["f"] = (today - dt.timedelta(days=_h(name) % cad if (first and cad > 1) else 0)).isoformat()
            fetched += 1
        except RateGuard as e:
            partial = True
            errors.append(f"rate guard stop: {e}")
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}: {e}")

    # drop per-repo source detail for repos that no longer exist / are not public
    live = {m["id"] for m in metas}
    per_repo = {k: v for k, v in per_repo.items() if k in live}
    series["repos"] = {k: v for k, v in series["repos"].items() if k in live}

    if agg_ref or fetched:
        sources["by_date"][today.isoformat()] = agg_ref
    for k in sorted(sources["by_date"])[:-cfg["keep_source_days"]]:
        del sources["by_date"][k]
    sources["repos"] = per_repo
    sources["updated"] = now.isoformat(timespec="seconds")

    hist[today.isoformat()] = [len(metas), sum(m["stars"] for m in metas), sum(m["forks"] for m in metas),
                               sum(m["watchers"] for m in metas), sum(m["issues"] for m in metas)]
    series["updated"] = now.isoformat(timespec="seconds")

    if login:
        try:
            prof = fetch_profile(gh, login)
            if prof:
                save(f"{D}/profile.json", prof, pretty=True)
        except RateGuard:
            partial = True
        except Exception as e:
            errors.append(f"profile: {type(e).__name__}: {e}")

    save(f"{D}/series.json", series)
    save(f"{D}/sources.json", sources)
    save(f"{D}/totals_history.json", hist)
    save(f"{D}/state.json", state)
    save(f"{D}/repos.json", metas)
    save(f"{D}/health.json", {
        "last_run": now.isoformat(timespec="seconds"), "repos_seen": len(metas),
        "traffic_fetched": fetched, "skipped_by_cadence": skipped,
        "api_calls": gh.calls, "rate_remaining": gh.remaining, "partial": partial,
        "seconds": round(time.time() - t0), "errors": errors[:20],
    }, pretty=True)
    hist_runs = load(f"{D}/run_history.json", [])
    hist_runs.append({"d": now.isoformat(timespec="seconds"), "repos": len(metas), "fetched": fetched,
                      "skipped": skipped, "calls": gh.calls, "left": gh.remaining, "s": round(time.time() - t0),
                      "partial": partial, "errors": len(errors), "full": bool(force)})
    save(f"{D}/run_history.json", hist_runs[-60:])
    print(f"public={len(metas)} fetched={fetched} skipped={skipped} calls={gh.calls} "
          f"remaining={gh.remaining} partial={partial} errors={len(errors)}")
