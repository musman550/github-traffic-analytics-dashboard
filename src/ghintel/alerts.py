"""Alerts that are worth a notification: failed/partial runs, big traffic spikes, finished weekly reports.
compute() is pure (easy to test); deliver() sends each title once (titles are remembered in alerts_sent.json)."""
import datetime as dt, statistics as st
from . import content as C, notify
from .store import load, save

SENT = "docs/data/alerts_sent.json"


def compute(s, health, reports, base, opt=None, log=None):
    out = []
    day = (health.get("last_run") or "")[:10]
    if health.get("partial") or health.get("errors"):
        errs = "; ".join(health.get("errors", [])[:8]) or "run stopped early"
        out.append((f"Collection run had problems on {day}",
                    f"The daily collection finished with warnings: {errs}.\n\nRepositories fetched: {health.get('traffic_fetched')}; "
                    f"API budget left: {health.get('rate_remaining')}. See {base}status/."))
    daily = s.get("daily", [])
    if len(daily) > 20:
        hist = [r[1] for r in daily[-63:-3]]
        if len(hist) >= 14 and st.pstdev(hist) > 0:
            mu, sd = st.mean(hist), st.pstdev(hist)
            for d, v, *_ in daily[-3:]:
                if v >= 30 and v > mu + 3 * sd:
                    out.append((f"Traffic spike on {d}",
                                f"{d} had {v:,} views, far above the recent average of {round(mu):,} per day. "
                                f"Open the dashboard: {base}#trends"))
    if reports:
        w = reports[0]
        end = (w["start"] + dt.timedelta(days=6)).isoformat()
        out.append((f"Weekly report: {w['start'].isoformat()} to {end}",
                    f"{C.report_summary(w)}\n\nFull report: {base}reports/{C.report_slug(w)}/"))
    if opt and opt.get("mode") == "live" and (opt["counts"].get("applied") or opt["counts"].get("prs")):
        day = opt["last_run"][:10]
        rows = [e for e in (log or []) if e.get("date") == day and e.get("mode") == "live" and e.get("status") in ("applied", "pending_pr")]
        lines = []
        for e in rows[:15]:
            what = ", ".join(k for k in ("description", "topics") if k in e.get("changes", {})) or "README proposal"
            pr = (e.get("readme") or {}).get("url")
            lines.append(f"- {e['repo']}: {what}" + (f" (PR: {pr})" if pr else ""))
        out.append((f"Optimizer run {day}: {opt['counts'].get('applied', 0)} repositories updated, {opt['counts'].get('prs', 0)} README pull requests",
                    "\n".join(lines) + f"\n\nDetails and rollback rules: {base}optimizer/"))
    return out


def deliver(cfg, items):
    sent = load(SENT, [])
    n = 0
    for title, body in items:
        if title in sent:
            continue
        ok = False
        if cfg.get("notifications", {}).get("issues"):
            ok = notify.issue(cfg["repo_full_name"], title, body) or ok
        if cfg.get("notifications", {}).get("telegram"):
            ok = notify.telegram(f"{title}\n\n{body}") or ok
        if ok:
            sent.append(title)
            n += 1
    save(SENT, sent[-200:])
    return n


def run(cfg):
    s = load("docs/data/summary.json")
    from .content import weekly_reports
    items = compute(s, load("docs/data/health.json", {}), weekly_reports(s), cfg["site_url"],
                    load("docs/data/optimizer_state.json"), load("docs/data/optimizer_log.json", []))
    print(f"alerts: {len(items)} candidate(s), {deliver(cfg, items)} sent")
