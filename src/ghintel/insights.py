"""Deterministic, data-backed insights. Every sentence is computed from collected numbers;
nothing is emitted unless the data supports it."""
import datetime as dt, statistics as st


def seo_audit(m, today):
    miss, pts = [], 0
    d = (m.get("desc") or "").strip()
    if d:
        pts += 25
        if 40 <= len(d) <= 160:
            pts += 10
        else:
            miss.append(f"Description is {len(d)} characters; 40-160 reads best in search results")
    else:
        miss.append("Add a repository description")
    n = len(m.get("topics") or [])
    pts += min(20, n * 2.5)
    if n < 8:
        miss.append(f"Add topics ({n} now; 8-15 recommended)")
    if m.get("license"):
        pts += 10
    else:
        miss.append("Add a license")
    if m.get("homepage"):
        pts += 10
    else:
        miss.append("Set a homepage URL")
    try:
        age = (today - dt.date.fromisoformat(m["pushed"])).days
    except Exception:
        age = 999
    if age <= 90:
        pts += 15
    else:
        miss.append(f"No push for {age} days")
    return {"score": round(pts * 100 / 90), "missing": miss}


def build_insights(T, repos, daily, sources, last, today):
    out = []
    pub = [r for r in repos if not r["fork"] and not r["archived"]]
    n = len(pub)

    def add(kind, title, text):
        out.append({"kind": kind, "title": title, "text": text})

    # traffic momentum
    v7, p7 = T["views_7d"], T["views_prev7"]
    if p7 >= 20 or v7 >= 20:
        if p7:
            ch = round((v7 - p7) * 100 / p7)
            add("trend", "Weekly momentum",
                f"Views over the last 7 complete days were {v7:,} versus {p7:,} the week before "
                f"({'+' if ch >= 0 else ''}{ch}%).")
    # concentration
    tot30 = sum(r["v30"] for r in repos)
    if tot30 >= 30:
        best = max(repos, key=lambda r: r["v30"])
        add("focus", "Where traffic comes from",
            f"{best['name']} earned {best['v30']:,} of {tot30:,} views in 30 days "
            f"({round(best['v30'] * 100 / tot30)}%).")
        top5 = sorted(repos, key=lambda r: -r["v30"])[:5]
        share = sum(r["v30"] for r in top5) * 100 / tot30
        add("focus", "Concentration", f"The 5 most viewed repositories hold {round(share)}% of 30-day views.")
    # zero-traffic repos
    if n:
        z = sum(1 for r in pub if r["v30"] == 0)
        add("health", "Repositories without views",
            f"{z} of {n} public repositories had no views in the last 30 days ({round(z * 100 / n)}%).")
    # clones vs views
    if T["views_30d"] >= 20 and T["clones_30d"] > T["views_30d"] * 5:
        add("note", "Clones far exceed views",
            f"There were {T['clones_30d']:,} clones against {T['views_30d']:,} views in 30 days. "
            "A gap this large usually means automation, CI jobs or crawlers cloning repositories, "
            "so views are the more reliable signal of human interest.")
    # sources
    if sources:
        tot = sum(s[1] for s in sources)
        if tot >= 10:  # too few referrals would make percentages misleading
            top = sources[0]
            add("sources", "Top referrer",
                f"{top[0]} sent {top[1]:,} of {tot:,} referred visits in the latest 14-day window "
                f"({round(top[1] * 100 / tot)}%).")
            g = T["google_14d"]
            add("sources", "Google search",
                f"Google referred {g:,} visits in the latest 14-day window ({round(g * 100 / tot)}% of referrals)."
                if g else "No visits attributed to Google in the latest 14-day window.")
    # weekday pattern (last 90 days)
    wd = [0] * 7
    for d, v, *_ in daily[-90:]:
        wd[dt.date.fromisoformat(d).weekday()] += v
    if sum(wd) >= 50:
        names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        add("pattern", "Busiest weekday",
            f"{names[wd.index(max(wd))]} has the most views over the last 90 days "
            f"({round(max(wd) * 100 / sum(wd))}% of the total).")
    # anomalies
    vals = [x[1] for x in daily[-60:]]
    if len(vals) >= 14 and st.pstdev(vals) > 0:
        mu, sd = st.mean(vals), st.pstdev(vals)
        spikes = [(d, v) for d, v, *_ in daily[-60:] if v > mu + 2.5 * sd and v >= 10]
        if spikes:
            d, v = max(spikes, key=lambda x: x[1])
            add("anomaly", "Traffic spike", f"{d} had {v:,} views, well above the 60-day average of {round(mu):,}.")
    # publishing cadence
    recent = [r for r in repos if r["created"] and (today - dt.date.fromisoformat(r["created"])).days <= 14]
    if recent:
        add("cadence", "Publishing cadence",
            f"{len(recent)} repositories were created in the last 14 days "
            f"(about {len(recent) / 14:.1f} per day).")
    # SEO hygiene
    if n:
        nd = sum(1 for r in pub if "Add a repository description" in r["audit"]["missing"])
        low_t = sum(1 for r in pub if len(r["topics"]) < 8)
        add("seo", "Metadata hygiene",
            f"{low_t} of {n} public repositories have fewer than 8 topics"
            + (f" and {nd} have no description." if nd else "; all have descriptions."))
    return out
