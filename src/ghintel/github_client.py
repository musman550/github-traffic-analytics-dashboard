import os, time, requests

API = "https://api.github.com"


class RateGuard(Exception):
    """Raised when the remaining API budget is too low to continue safely."""


class GH:
    def __init__(self, token=None, min_remaining=300, sleep=0.1):
        token = token or os.environ.get("GH_PAT")
        if not token:
            raise SystemExit("GH_PAT is not set")
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "github-traffic-analytics-dashboard",
        })
        self.remaining = None
        self.min_remaining = min_remaining
        self.sleep = sleep
        self.calls = 0

    def get(self, path, params=None, retries=3):
        """Return (json|None, response). None for 403/404 that are not rate limits."""
        url = path if path.startswith("http") else API + path
        last = None
        for attempt in range(retries + 1):
            if self.remaining is not None and self.remaining < self.min_remaining:
                raise RateGuard(f"remaining={self.remaining}")
            try:
                r = self.s.get(url, params=params, timeout=30)
            except requests.RequestException as e:
                last = e
                time.sleep(2 ** attempt)
                continue
            self.calls += 1
            if "x-ratelimit-remaining" in r.headers:
                self.remaining = int(r.headers["x-ratelimit-remaining"])
            time.sleep(self.sleep)
            if r.status_code == 200:
                return r.json(), r
            if r.status_code == 401:
                raise SystemExit("GitHub rejected the token (401). Create a new token with the 'repo' scope "
                                 "and update the GH_PAT secret.")
            if r.status_code in (403, 429):
                text = r.text.lower()
                if self.remaining == 0:
                    raise RateGuard("primary rate limit exhausted")
                if "rate limit" in text or "abuse" in text or r.headers.get("retry-after"):
                    wait = min(int(r.headers.get("retry-after", 60)), 120)
                    time.sleep(wait)
                    continue
                return None, r
            if r.status_code == 404:
                return None, r
            if r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            return None, r
        if last:
            raise last
        return None, None

    def text(self, path, accept="application/vnd.github.raw+json"):
        """GET raw text (e.g. README). Returns None on 404/403."""
        if self.remaining is not None and self.remaining < self.min_remaining:
            raise RateGuard(f"remaining={self.remaining}")
        r = self.s.get(API + path, headers={"Accept": accept}, timeout=30)
        self.calls += 1
        if "x-ratelimit-remaining" in r.headers:
            self.remaining = int(r.headers["x-ratelimit-remaining"])
        time.sleep(self.sleep)
        return r.text if r.status_code == 200 else None

    def graphql(self, query):
        if self.remaining is not None and self.remaining < self.min_remaining:
            raise RateGuard(f"remaining={self.remaining}")
        r = self.s.post(API + "/graphql", json={"query": query}, timeout=30)
        self.calls += 1
        time.sleep(self.sleep)
        if r.status_code != 200:
            return None
        return r.json().get("data")

    def paginate(self, path, params=None):
        out, url = [], path
        params = dict(params or {})
        while url:
            data, r = self.get(url, params)
            if data is None:
                break
            out.extend(data)
            nxt = r.links.get("next", {}).get("url")
            url, params = nxt, None
        return out
