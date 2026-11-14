"""Fetch the owner's public profile and every public link on it. Nothing is invented:
links come only from the GitHub profile, its social accounts, and the profile README."""
import re
from urllib.parse import urlparse

SOCIAL = {
    "youtube.com": "YouTube", "youtu.be": "YouTube", "linkedin.com": "LinkedIn",
    "instagram.com": "Instagram", "twitter.com": "X (Twitter)", "x.com": "X (Twitter)",
    "facebook.com": "Facebook", "tiktok.com": "TikTok", "t.me": "Telegram", "telegram.me": "Telegram",
    "discord.gg": "Discord", "discord.com": "Discord", "medium.com": "Medium", "dev.to": "DEV",
    "reddit.com": "Reddit", "mastodon.social": "Mastodon", "bsky.app": "Bluesky",
    "threads.net": "Threads", "pinterest.com": "Pinterest", "twitch.tv": "Twitch",
    "hashnode.dev": "Hashnode", "substack.com": "Substack", "github.com": "GitHub",
    "huggingface.co": "Hugging Face", "kaggle.com": "Kaggle", "wa.me": "WhatsApp",
    "blogspot.com": "Blogger", "wordpress.com": "WordPress", "buymeacoffee.com": "Buy Me a Coffee",
}
SKIP = ("shields.io", "img.shields.io", "badge", "visitor-badge", "komarev.com", "camo.githubusercontent")
LINK = re.compile(r"(?<!!)\[([^\]]*)\]\((https?://[^)\s]+)\)")
BARE = re.compile(r"""(?<![\("'=])\bhttps?://[^\s<>)"']+""")


def norm(url):
    url = (url or "").strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def provider_for(url):
    host = (urlparse(url).netloc or "").lower().removeprefix("www.")
    for dom, name in SOCIAL.items():
        if host == dom or host.endswith("." + dom):
            return name
    return None


def fetch_profile(gh, login):
    u, _ = gh.get(f"/users/{login}")
    if not u:
        return None
    socials, _ = gh.get(f"/users/{login}/social_accounts")
    readme = gh.text(f"/repos/{login}/{login}/readme")

    links, seen = [], set()

    def add(url, label=None, kind=None, source="profile"):
        url = norm(url)
        if not url or any(s in url for s in SKIP):
            return
        key = url.lower().rstrip("/")
        if key in seen:
            return
        seen.add(key)
        prov = provider_for(url)
        if kind is None:
            kind = "social" if prov and prov != "GitHub" else "website"
        links.append({"url": url, "label": label or prov or urlparse(url).netloc.removeprefix("www."),
                      "provider": prov, "kind": kind, "source": source})

    add(u.get("blog"), None, "website", "profile website")
    if u.get("twitter_username"):
        add(f"https://x.com/{u['twitter_username']}", "X (Twitter)", "social", "profile")
    for s in socials or []:
        add(s.get("url"), None, None, "profile social accounts")

    featured = []
    if readme:
        for label, url in LINK.findall(readme):
            label = re.sub(r"[*_`]", "", label).strip()
            m = re.match(r"https://github\.com/%s/([\w.\-]+)/?$" % re.escape(login), url, re.I)
            if m and m.group(1).lower() != login.lower():
                if m.group(1) not in [f["repo"] for f in featured]:
                    featured.append({"repo": m.group(1), "label": label or m.group(1)})
                continue
            add(url, None, None, "profile README")
        for url in BARE.findall(readme):
            if not re.match(r"https://github\.com/%s/" % re.escape(login), url, re.I):
                add(url, None, None, "profile README")

    return {
        "login": login, "name": u.get("name") or login, "company": u.get("company"),
        "bio": u.get("bio"), "location": u.get("location"), "avatar": u.get("avatar_url"),
        "url": u.get("html_url"), "followers": u.get("followers", 0),
        "public_repos": u.get("public_repos", 0), "created": (u.get("created_at") or "")[:10],
        "tagline": _tagline(readme), "links": links, "featured": featured[:4],
    }


def _tagline(readme):
    """First plain sentence of the profile README, if any (used as the about text)."""
    for line in (readme or "").splitlines():
        s = line.strip()
        if s and not s.startswith(("#", "!", "[", "<", "-", "*", "|", ">", "`")) and len(s) > 20:
            return re.sub(r"[*_`]", "", s)[:300]
    return None
