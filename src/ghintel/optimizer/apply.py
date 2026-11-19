"""Write changes back to GitHub: metadata directly (logged, reversible) and README text through pull requests."""
import base64, datetime as dt, re
from .generate import is_junk_topic, weak_description


def merge_topics(current, proposed, max_topics):
    out = list(current)
    for t in proposed:
        if len(out) >= max_topics:
            break
        if t not in out:
            out.append(t)
    return out


def metadata_changes(ctx, prop, ranked_topics, ocfg):
    ch = {}
    d = prop.get("description")
    if d and d != ctx["desc"] and (ocfg["description_policy"] == "always" or weak_description(ctx["desc"])):
        ch["description"] = {"before": ctx["desc"], "after": d}
    # remove only clear junk (1-2 character words, stop words, bare numbers); everything else is kept
    junk = [t for t in ctx["topics"] if is_junk_topic(t)] if ocfg.get("remove_junk_topics", True) else []
    kept = [t for t in ctx["topics"] if t not in junk]
    after = merge_topics(kept, ranked_topics, ocfg["max_topics"])
    if after != ctx["topics"]:
        ch["topics"] = {"before": ctx["topics"], "after": after}
        if junk:
            ch["topics"]["removed"] = junk
    return ch


def tokens(s):
    return set(t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) > 2)


def related(summary_repos, ctx, ocfg, classify, n=3):
    mine = set(ctx["topics"]) | tokens(ctx["name"])
    cand = []
    for r in summary_repos:
        if r["name"] == ctx["name"] or r["name"] in ocfg["exclude"] or r["fork"] or r["archived"] or classify(r["name"], ocfg) != "product":
            continue
        other = set(r["topics"]) | tokens(r["name"])
        j = len(mine & other) / max(1, len(mine | other))
        cand.append((j, r))
    cand.sort(key=lambda x: (-x[0], x[1]["name"]))
    return [r for j, r in cand[:n] if j > 0] or [r for _, r in cand[:n]]


def build_block(ctx, prop, all_topics, rel, website, ocfg, base):
    lines = []
    if prop.get("summary"):
        lines.append(f"> **Summary:** {prop['summary']}")
    if all_topics:
        lines.append("**Keywords:** " + " · ".join(all_topics))
    faq = prop.get("faq") or []
    if faq:
        lines.append("### FAQ")
        for f in faq:
            lines.append(f"**{f['q']}**  \n{f['a']}")
    links = []
    if rel:
        links += [f"- [{r['name']}]({r['url']})" + (f": {r['desc'][:120]}" if r.get("desc") and not weak_description(r["desc"]) else "") for r in rel]
    if website:
        links.append(f"- [Website]({website})")
    if links and (prop.get("summary") or faq):
        lines.append("### Related projects\n" + "\n".join(links))
    if not (prop.get("summary") or faq):
        return ""
    lines.append(f"<sub>Generated automatically from this repository's own content. [How this works]({base}optimizer/)</sub>")
    return ocfg["block_start"] + "\n" + "\n\n".join(lines) + "\n" + ocfg["block_end"]


def upsert_block(readme, block, start, end):
    """Insert or replace the managed block. A new block goes after the introduction (before the first
    second-level heading) so the title and tagline stay together; with no such heading it goes last."""
    if not block:
        return readme
    if start in readme and end in readme:
        return re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block, readme, count=1, flags=re.S)
    h1 = re.search(r"^# .+$", readme, flags=re.M)
    pos = h1.end() if h1 else 0
    h2 = re.search(r"^## .+$", readme[pos:], flags=re.M)
    if h2:
        i = pos + h2.start()
        return readme[:i].rstrip("\n") + "\n\n" + block + "\n\n" + readme[i:]
    return readme.rstrip("\n") + "\n\n" + block + "\n"


def open_readme_pr(gw, ctx, new_text, ocfg, today, why):
    """Create a branch, commit the README change and open a pull request. Returns dict or None."""
    full = ctx["full"]
    data, _ = gw.get(f"/repos/{full}/git/ref/heads/{ctx['branch']}")
    if not data:
        return None
    sha = data["object"]["sha"]
    branch = f"{ocfg['branch_prefix']}{today.strftime('%Y%m%d')}"
    code, _ = gw.send("POST", f"/repos/{full}/git/refs", {"ref": f"refs/heads/{branch}", "sha": sha})
    if code not in (200, 201):
        return None
    rd, _ = gw.get(f"/repos/{full}/readme")
    path = rd["path"] if rd else "README.md"
    body = {"message": "docs: add auto-generated summary and related projects", "branch": branch,
            "content": base64.b64encode(new_text.encode()).decode()}
    if rd:
        body["sha"] = rd["sha"]
    code, _ = gw.send("PUT", f"/repos/{full}/contents/{path}", body)
    if code not in (200, 201):
        return None
    code, pr = gw.send("POST", f"/repos/{full}/pulls", {
        "title": "Add auto-generated summary and related projects to README", "head": branch, "base": ctx["branch"],
        "body": why + "\n\nOnly the block between the AUTO-SEO markers is managed. Close this pull request to decline; "
                      "the optimizer will not propose README changes for this repository again for a while."})
    if code not in (200, 201) or not isinstance(pr, dict):
        return None
    return {"number": pr["number"], "url": pr["html_url"], "repo": full, "status": "pending", "opened": today.isoformat()}
