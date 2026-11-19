"""Turn repository facts into safe metadata proposals: AI first (with validation and an independent
fact-check), deterministic rules as the always-available fallback."""
import re
from ..ai.router import AllFailed

HYPE = re.compile(r"\b(best|#1|ultimate|guarantee[ds]?|revolutionary|perfect|100%|world[- ]class|game[- ]?chang\w*|unmatched|magic(al)?|blazing)\b", re.I)
URL = re.compile(r"https?://", re.I)
TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")
GENERIC_OK = {"python", "javascript", "typescript", "html", "css", "shell", "docker", "open-source", "api", "github-actions", "github"}
STOP = set("the a an and or of to for in on with by from is are be this that it its as at your you my our how what why new using use via vs get just now".split())

KNOWN = {  # phrase found in README -> topic (only used when the phrase is really there)
    "model context protocol": "model-context-protocol", "mcp": "mcp", "n8n": "n8n", "fastapi": "fastapi", "flask": "flask",
    "docker": "docker", "telegram": "telegram-bot", "chatbot": "chatbot", "ai agent": "ai-agents", "llm": "llm",
    "automation": "automation", "workflow": "workflow-automation", "seo": "seo", "cli": "cli", "command line": "cli",
    "playwright": "playwright", "selenium": "selenium", "web scraping": "web-scraping", "scraper": "web-scraping",
    "github actions": "github-actions", "openai": "openai", "claude": "claude", "gemini": "gemini", "ollama": "ollama",
    "whatsapp": "whatsapp", "youtube": "youtube", "wordpress": "wordpress", "blogger": "blogger", "next.js": "nextjs",
    "react": "react", "node.js": "nodejs", "vercel": "vercel", "cloudflare": "cloudflare", "sqlite": "sqlite",
    "rest api": "rest-api", "webhook": "webhooks", "voice": "voice-ai", "text-to-speech": "text-to-speech", "tts": "text-to-speech",
    "transformer": "transformers", "huggingface": "huggingface", "rag": "rag", "vector": "vector-database",
}


def clean_readme(text, start, end, limit=4500):
    t = text or ""
    t = re.sub(re.escape(start) + r".*?" + re.escape(end), "", t, flags=re.S)
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"<img[^>]*>", "", t, flags=re.I)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if len(t) > limit:
        cut = t[:limit]
        t = cut[:cut.rfind("\n\n")] if "\n\n" in cut[limit // 2:] else cut
    return t


def words(text):
    return set(re.findall(r"[a-z0-9][a-z0-9.+#]*", (text or "").lower()))


BOILER = re.compile(r"\b(curated|written|published|generated|built|made|created|maintained|powered)( and \w+)* by\b|^all rights|^licensed? ", re.I)
OVERVIEW_H = re.compile(r"^#{1,3}\s*(overview|about|description|introduction|summary|what is[^\n]*)\s*$", re.I | re.M)
WEAK_TOPICS = {"youtube", "seo", "github-actions", "react", "vercel", "cloudflare", "openai", "gemini"}
GENERIC_NAME = {"server", "status", "tool", "tools", "free", "assets", "site", "backend", "release", "releases", "weekly", "daily"}
JUNK_TOPIC = set("a an the of to in on at is it as or and for with by from this that when just now new how what why".split())


def smart_cut(s, maxlen=160):
    """Shorten at a natural boundary instead of mid-phrase."""
    s = s.strip()
    if len(s) <= maxlen:
        return s
    cut = s[:maxlen]
    for sep in (". ", "; ", " — ", " - ", ", ", ": "):
        k = cut.rfind(sep)
        if k >= 60:
            return cut[:k].rstrip(" ,;:-—") + ("." if sep == ". " else "")
    return cut.rsplit(" ", 1)[0].rstrip(" ,;:-—")


def _clean_para(p):
    p = re.sub(r"^>+\s*", "", p.strip())
    p = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", p)
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", p)).strip()


def first_sentence(readme, maxlen=160):
    text = readme or ""
    m = OVERVIEW_H.search(text)
    chunks = re.split(r"\n\s*\n", text[m.end():] if m else text)
    for para in chunks:
        raw = para.strip()
        if not raw or raw.startswith(("#", "```", "|", "<", "![", "- ", "* ", "---", "**Source", "**Total", "**Last")):
            continue
        p = _clean_para(raw)
        if len(p) < 25 or BOILER.search(p):
            continue
        mm = re.match(r"(.+?[.!?])(\s|$)", p)
        s = mm.group(1) if mm and len(mm.group(1)) >= 40 else p
        return smart_cut(s, maxlen)
    return ""


def is_junk_topic(t):
    return len(t) <= 2 or t in JUNK_TOPIC or t.isdigit()


def topic_ok(t, text_words):
    if not TOPIC_RE.match(t):
        return False
    if t in GENERIC_OK:
        return True
    for tok in t.split("-"):
        if tok.isdigit():
            continue
        if not (tok in text_words or tok.rstrip("s") in text_words or tok + "s" in text_words):
            return False
    return True


def weak_description(d):
    d = (d or "").strip()
    return (len(d) < 40 or len(d) > 200 or URL.search(d) or d.endswith(("…", "...", ",")) or "\n" in d or bool(re.search(r"[*_`#]", d)))


def source_words(ctx):
    return words(" ".join([ctx["name"].replace("-", " "), ctx.get("desc", ""), ctx.get("readme", ""),
                           ctx.get("lang") or "", " ".join(ctx.get("files", [])), " ".join(ctx.get("topics", []))]))


def validate(obj, ctx):
    """Raise ValueError when a proposal is unsafe. Used both on AI output and on rule output."""
    sw = source_words(ctx)
    d = obj.get("description")
    if d is not None:
        if not isinstance(d, str) or not 30 <= len(d.strip()) <= 160:
            raise ValueError("description must be 30-160 characters")
        if "\n" in d or URL.search(d) or HYPE.search(d) or re.search(r"[*_`#<>]", d):
            raise ValueError("description has markup, links or hype")
        if not (words(d) & (sw - STOP)):
            raise ValueError("description shares nothing with the repository")
    ts = obj.get("topics", [])
    if not isinstance(ts, list) or len(ts) > 15 or any(not isinstance(x, str) for x in ts):
        raise ValueError("topics must be a short list of strings")
    bad = [x for x in ts if not topic_ok(x, sw)]
    if bad:
        raise ValueError(f"topics not grounded in the repository: {bad[:4]}")
    s = obj.get("summary", "") or ""
    if s and (len(s) > 260 or (URL.search(s) and not URL.search(ctx.get("readme", ""))) or HYPE.search(s)):
        raise ValueError("summary too long, hype or unsupported link")
    faq = obj.get("faq", []) or []
    if not isinstance(faq, list) or len(faq) > 3:
        raise ValueError("faq must have at most 3 items")
    rd = ctx.get("readme", "")
    for f in faq:
        if not isinstance(f, dict) or not str(f.get("q", "")).strip().endswith("?") or not 10 <= len(str(f.get("a", ""))) <= 300:
            raise ValueError("faq item malformed")
        if HYPE.search(str(f["a"])) or (URL.search(str(f["a"])) and not URL.search(rd)):
            raise ValueError("faq answer has hype or unsupported link")
        for num in re.findall(r"\d[\d.,]*", str(f["a"])):
            if num.strip(".,") not in rd and num.strip(".,") not in ctx.get("desc", ""):
                raise ValueError(f"faq answer contains a number not found in the README: {num}")
    return obj


def sanitize(obj, ctx):
    """Keep every valid part of a proposal and drop invalid parts (instead of rejecting everything).
    Returns (clean, dropped_reasons)."""
    clean, dropped = {"description": None, "topics": [], "summary": "", "faq": []}, []
    d = obj.get("description")
    if d:
        try:
            validate({"description": d, "topics": []}, ctx)
            clean["description"] = d.strip()
        except ValueError as e:
            dropped.append(f"description: {e}")
    sw = source_words(ctx)
    for tpc in obj.get("topics") or []:
        if isinstance(tpc, str) and topic_ok(tpc, sw):
            if tpc not in clean["topics"]:
                clean["topics"].append(tpc)
        else:
            dropped.append(f"topic {tpc!r}")
    s = obj.get("summary") or ""
    if s:
        try:
            validate({"topics": [], "summary": s}, ctx)
            clean["summary"] = s
        except ValueError as e:
            dropped.append(f"summary: {e}")
    for f in (obj.get("faq") or [])[:3]:
        try:
            validate({"topics": [], "faq": [f]}, ctx)
            clean["faq"].append(f)
        except ValueError as e:
            dropped.append(f"faq: {e}")
    return clean, dropped


def require_value(clean):
    if not (clean["description"] or clean["topics"] or clean["summary"] or clean["faq"]):
        raise ValueError("nothing usable after validation")


SYSTEM = ("You are a careful technical writer who improves GitHub repository metadata. Use ONLY facts stated in the "
          "repository content you are given. Never invent features, numbers, benchmarks, integrations, customers or claims. "
          "No marketing hype. Plain text, no markdown, no emoji. Reply with exactly one JSON object and nothing else.")


def prompt(ctx, full):
    schema = ('{"description": "40-160 characters, main keyword first, factual", '
              '"topics": ["up to 8 NEW lowercase-hyphenated GitHub topics, each describing something stated in the content"]'
              + (', "summary": "1-2 factual sentences, max 240 characters", '
                 '"faq": [{"q": "question ending with ?", "a": "answer taken from the README, max 280 characters"}]}' if full else "}"))
    return (f"Repository: {ctx['name']}\nLanguage: {ctx.get('lang') or 'unknown'}\n"
            f"Current description: {ctx.get('desc') or '(none)'}\nExisting topics (do not repeat): {', '.join(ctx.get('topics', [])) or '(none)'}\n"
            f"Top-level files: {', '.join(ctx.get('files', [])[:20]) or '(unknown)'}\n\nREADME excerpt:\n---\n{ctx.get('readme') or '(no README)'}\n---\n\n"
            f"Return JSON with this shape:\n{schema}\n"
            + ("Rules: faq has 0-3 items and only questions the README actually answers; use an empty list if it does not. " if full else "")
            + "Rules: topics must be words that appear in the content; keep the description natural, not keyword-stuffed.")


def rule_proposal(ctx):
    """Deterministic fallback. Conservative: topics need repeated evidence in the README, descriptions
    are only replaced when the current one is weak."""
    sw = source_words(ctx)
    text = " " + (ctx.get("readme", "") + " " + ctx.get("desc", "")).lower() + " "
    name = ctx["name"].lower().replace("-", " ")

    def count(phrase):
        return len(re.findall(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text))
    new = []
    for phrase, topic in KNOWN.items():
        need = 3 if topic in WEAK_TOPICS else 2
        if (count(phrase) >= need or (phrase in name and count(phrase) >= 1)) and topic not in new:
            new.append(topic)
    lang = (ctx.get("lang") or "").lower()
    if lang and TOPIC_RE.match(lang) and lang not in new:
        new.append(lang)
    for tok in re.findall(r"[a-z0-9]+", ctx["name"].lower()):
        if len(tok) > 3 and tok not in STOP and tok not in GENERIC_NAME and tok not in new and count(tok) >= 2 and tok not in ("musfira", "musfiraai"):
            new.append(tok)
    existing = set(ctx.get("topics", []))
    new = [t for t in new if t not in existing and topic_ok(t, sw)][:6]
    prop = {"topics": new, "summary": "", "faq": [], "source": "rules"}
    if weak_description(ctx.get("desc")):
        d = first_sentence(ctx.get("readme", ""))
        if d and 30 <= len(d) <= 160:
            prop["description"] = d
    return prop


def judge(router, ctx, prop, avoid_model=None):
    """Fact-check by the strongest available model that is not the generator. Returns a 1-5 support score."""
    claim = {k: prop.get(k) for k in ("description", "topics", "summary", "faq") if prop.get(k)}
    system = ("You verify claims about a GitHub repository against its README. Reply with one JSON object: "
              '{"score": 1-5, "unsupported": ["claims that are clearly NOT in the README"]}. '
              "5 = every claim is stated or clearly implied by the README; 3 = some claims are stretched; "
              "1 = the proposal contradicts or invents things. List only claims that are really absent or contradicted; "
              "paraphrases and reasonable summaries of README content are supported.")
    user = f"README excerpt:\n---\n{ctx.get('readme', '')}\n---\nRepository name: {ctx['name']}\nProposed metadata (JSON): {claim}"
    for am in (avoid_model, None):
        try:
            out, meta = router.chat_json("judge" + ("" if am else "-any"), system, user, required=("score",), max_tokens=300,
                                         temperature=0, avoid_model=am)
            try:
                score = int(out.get("score"))
            except (TypeError, ValueError):
                score = 3
            return {"score": score, "faithful": score >= 3, "unsupported": [str(x)[:120] for x in (out.get("unsupported") or [])[:5]],
                    "by": meta.get("source", "")}
        except AllFailed:
            if am is None:
                break
    return {"score": None, "faithful": None, "unsupported": [], "by": "unavailable"}


def propose(router, ctx, full, use_judge=True, rules_only=False):
    """Returns (proposal, notes). AI output is sanitized (invalid parts dropped), fact-checked, and replaced by
    deterministic rules when nothing usable remains."""
    notes = []
    if not rules_only:
        def check(o):
            clean, _ = sanitize(_normalize(o, full), ctx)
            require_value(clean)
        try:
            raw, meta = router.chat_json("metadata", SYSTEM, prompt(ctx, full), required=("description", "topics"), validate=check, max_tokens=1500)
            clean, dropped = sanitize(_normalize(raw, full), ctx)
            clean["source"] = f"ai:{meta.get('source') or meta.get('provider')}"
            if dropped:
                notes.append("dropped: " + "; ".join(dropped)[:240])
            if use_judge and (clean["summary"] or clean["faq"] or clean["description"]):
                j = judge(router, ctx, clean, avoid_model=meta.get("model"))
                clean["judge"] = j
                if j["score"] is not None and j["score"] <= 2:
                    notes.append(f"judge score {j['score']}: " + "; ".join(j["unsupported"])[:200])
                    return _rules(ctx, notes), notes
                if j["score"] == 3:  # stretched claims: keep the safe parts, drop the riskiest
                    clean["faq"], clean["summary"] = [], ""
                    notes.append("judge score 3: dropped summary and FAQ")
            return clean, notes
        except AllFailed as e:
            notes.append(f"no AI provider produced a valid answer ({str(e)[:140]})")
    return _rules(ctx, notes), notes


def _normalize(o, full):
    fix = lambda s: str(s).replace('\\"', '"').strip()
    out = {"description": fix(o.get("description") or "") or None,
           "topics": [str(t).strip().lower().replace("_", "-").replace(" ", "-") for t in (o.get("topics") or [])][:15]}
    if full:
        out["summary"] = fix(o.get("summary") or "")
        out["faq"] = [{"q": fix(f.get("q", "")), "a": fix(f.get("a", ""))} for f in (o.get("faq") or []) if isinstance(f, dict)][:3]
    else:
        out["summary"], out["faq"] = "", []
    return out


def _rules(ctx, notes):
    p = rule_proposal(ctx)
    try:
        validate(p, ctx)
    except ValueError as e:
        notes.append(f"rules proposal trimmed: {e}")
        p = {"topics": [], "summary": "", "faq": [], "source": "rules"}
    return p
