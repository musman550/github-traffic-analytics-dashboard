"""Alerts that are worth a notification: failed/partial runs, big traffic spikes, finished weekly reports.
compute() is pure (easy to test); deliver() sends each title once (titles are remembered in alerts_sent.json)."""
import datetime as dt, statistics as st
from . import content as C, notify
from .store import load, save

SENT = "docs/data/alerts_sent.json"


def compute(s, health, reports, base):
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
    items = compute(s, load("docs/data/health.json", {}), weekly_reports(s), cfg["site_url"])
    print(f"alerts: {len(items)} candidate(s), {deliver(cfg, items)} sent")
