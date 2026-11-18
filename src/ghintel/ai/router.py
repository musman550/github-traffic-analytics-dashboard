"""Multi-provider LLM router for open-weight models with automatic fallback.

Design goals: never depend on one provider, never hit a free-tier limit twice, never crash the pipeline.
  * Providers speak the OpenAI-compatible chat API. A provider is used only when its key is present
    (GitHub Models needs no extra key inside GitHub Actions) and, by default, only for open-weight models.
  * 429 / quota -> cooldown (persisted between runs); 5xx -> short cooldown; 401/403 -> disabled for the run;
    unknown model -> next model; invalid or rejected output -> next provider.
  * Per-provider request spacing (rpm) and a daily call budget, response cache, live stats for the status pages.
Nothing here ever raises to the caller except AllFailed, which the optimizer answers with a rule-based fallback.
"""
import copy, datetime as dt, hashlib, json, os, re, time, urllib.error, urllib.request

OPEN_RE = re.compile(r"llama|deepseek|mistral|mixtral|nemo|phi-?\d|qwen|gemma|gpt-oss|glm|kimi", re.I)
PREFER_RE = [re.compile(p, re.I) for p in (r"llama-?3\.3.*70b", r"llama-?4", r"gpt-oss-120b", r"qwen.*(72b|235b|32b)",
                                           r"deepseek-?v3", r"mistral-?small", r"phi-?4", r"llama-?3\.1.*(70|8)b")]

DEFAULT_PROVIDERS = [
    {"name": "groq", "base": "https://api.groq.com/openai/v1", "keys": ["GROQ_API_KEY"], "open": True,
     "models": ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"], "rpm": 20, "daily": 800, "json": True},
    {"name": "cerebras", "base": "https://api.cerebras.ai/v1", "keys": ["CEREBRAS_API_KEY"], "open": True,
     "models": ["gpt-oss-120b", "llama-3.3-70b", "qwen-3-32b"], "rpm": 20, "daily": 800, "json": True},
    {"name": "github-models", "base": "https://models.github.ai/inference", "keys": ["GITHUB_MODELS_TOKEN"], "open": True,
     "models": ["meta/Llama-3.3-70B-Instruct", "meta/Llama-4-Scout-17B-16E-Instruct", "deepseek/DeepSeek-V3-0324", "mistral-ai/Mistral-Small-2503"],
     "discover": "github-models", "rpm": 10, "daily": 100, "json": True,
     "headers": {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}},
    {"name": "ovhcloud", "base": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1", "keys": [], "anon": True, "open": True,
     "models": ["Meta-Llama-3_3-70B-Instruct", "Mistral-7B-Instruct-v0.3", "Qwen2.5-Coder-32B-Instruct"], "discover": "openai-models",
     "rpm": 2, "daily": 40, "json": False},
    {"name": "pollinations", "base": "https://text.pollinations.ai/openai", "path": "", "keys": [], "anon": True, "open": True,
     "models": ["mistral", "llama"], "discover": "pollinations", "rpm": 4, "daily": 60, "json": False},
    {"name": "openrouter", "base": "https://openrouter.ai/api/v1", "keys": ["OPENROUTER_API_KEY"], "open": True,
     "models": ["meta-llama/llama-3.3-70b-instruct:free"], "discover": "openrouter", "rpm": 12, "daily": 40, "json": False,
     "headers": {"HTTP-Referer": "https://github.com/musman550/github-traffic-analytics-dashboard", "X-Title": "Traffic dashboard optimizer"}},
    {"name": "huggingface", "base": "https://router.huggingface.co/v1", "keys": ["HF_TOKEN"], "open": True,
     "models": ["meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct"], "rpm": 10, "daily": 100, "json": False},
    {"name": "mistral", "base": "https://api.mistral.ai/v1", "keys": ["MISTRAL_API_KEY"], "open": True,
     "models": ["open-mistral-nemo", "mistral-small-latest"], "rpm": 10, "daily": 200, "json": True},
    {"name": "cloudflare", "base": "https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1",
     "keys": ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"], "open": True, "token_env": "CLOUDFLARE_API_TOKEN",
     "models": ["@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/meta/llama-3.1-8b-instruct"], "rpm": 10, "daily": 150, "json": False},
    {"name": "gemini", "base": "https://generativelanguage.googleapis.com/v1beta/openai", "keys": ["GEMINI_API_KEY"], "open": False,
     "models": ["gemini-2.0-flash"], "rpm": 10, "daily": 200, "json": True},
]


class AllFailed(Exception):
    pass


def _loads(raw):
    try:
        return json.loads(raw)
    except Exception:
        return raw


def http_json(method, url, headers, body=None, timeout=45):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), _loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), _loads(e.read().decode("utf-8", "replace"))
    except Exception as e:  # network error, timeout, DNS
        return 0, {}, {"error": f"{type(e).__name__}: {e}"}


def extract_json(text):
    """Pull the first JSON object out of a model reply (handles code fences and chatter)."""
    if isinstance(text, dict):
        return text
    t = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        v = json.loads(t)
        return v if isinstance(v, dict) else None
    except Exception:
        pass
    a, b = t.find("{"), t.rfind("}")
    if a != -1 and b > a:
        try:
            v = json.loads(t[a:b + 1])
            return v if isinstance(v, dict) else None
        except Exception:
            return None
    return None


class Router:
    def __init__(self, cfg=None, state=None, cache=None, http=None, sleep=None, now=None, env=None):
        ai = (cfg or {}).get("ai", {})
        self.cfg = ai
        self.env = os.environ if env is None else env
        self.http, self.sleep, self.now = http or http_json, sleep or time.sleep, now or time.time
        self.state = state if state is not None else {}
        self.state.setdefault("providers", {})
        self.state.setdefault("discovered", {})
        self.cache = cache if cache is not None else {}
        self.timeout = ai.get("timeout", 45)
        self.allow_closed = ai.get("allow_closed_models", False)
        self.dead = set()
        self.last_call = {}
        self.calls = 0
        order = ai.get("order") or [p["name"] for p in DEFAULT_PROVIDERS]
        by = {p["name"]: copy.deepcopy(p) for p in DEFAULT_PROVIDERS}  # never mutate the shared defaults
        for name, over in (ai.get("providers") or {}).items():
            by.setdefault(name, {"name": name}).update(over)
        self.providers = [by[n] for n in order if n in by] + [p for n, p in by.items() if n not in order]

    # ------------------------------------------------------------ availability
    def _key(self, p):
        if p.get("anon"):  # keyless public tier (can be switched off with ai.anon_enabled=false)
            return [""] if self.cfg.get("anon_enabled", True) else None
        vals = [self.env.get(k, "") for k in p.get("keys", [])]
        return vals if vals and all(vals) else None

    def _st(self, name):
        return self.state["providers"].setdefault(name, {"ok": 0, "fail": 0, "bad": 0, "lat": 0, "streak": 0,
                                                          "last_error": "", "last_ok": "", "cool": 0, "day": {"d": "", "n": 0}})

    def _today(self):
        return dt.datetime.fromtimestamp(self.now(), dt.timezone.utc).strftime("%Y-%m-%d")

    def usable(self, p):
        if p["name"] in self.dead or (not p.get("open", True) and not self.allow_closed):
            return False
        if not self._key(p):
            return False
        st = self._st(p["name"])
        if st["cool"] > self.now():
            return False
        day = st["day"]
        if day["d"] == self._today() and day["n"] >= p.get("daily", 100):
            return False
        return True

    def ordered(self, prefer=None, avoid=None):
        ps = [p for p in self.providers if self.usable(p) and p["name"] != avoid]
        ps.sort(key=lambda p: (self._st(p["name"])["streak"] >= 3, 0 if p["name"] == prefer else 1))
        return ps

    def status(self):
        out = []
        for p in self.providers:
            st = self._st(p["name"])
            key = bool(self._key(p))
            out.append({"name": p["name"], "open_weight": p.get("open", True), "configured": key,
                        "ok": st["ok"], "fail": st["fail"], "bad": st["bad"], "avg_ms": st["lat"],
                        "cooldown": st["cool"] > self.now(), "last_error": st["last_error"], "last_ok": st["last_ok"],
                        "today": st["day"]["n"] if st["day"]["d"] == self._today() else 0, "daily_cap": p.get("daily", 100),
                        "discover_error": self.state.get("discover_error", {}).get(p["name"], "")})
        return out

    # ------------------------------------------------------------ models
    def models_for(self, p):
        name = p["name"]
        disc = self.state["discovered"].get(name)
        if disc and disc.get("d") == self._today() and disc.get("models"):
            return disc["models"]
        models = list(p.get("models", []))
        kind = p.get("discover")
        if kind:
            try:
                found = self._discover(p, kind)
                if found:
                    models = found + [m for m in models if m not in found]
                    self.state["discovered"][name] = {"d": self._today(), "models": models[:6]}
            except Exception:
                pass
        if not (p.get("open", True) or self.allow_closed):
            models = [m for m in models if OPEN_RE.search(m)]
        return models[:6]

    def _discover(self, p, kind):
        keyv = self._key(p)
        if kind == "github-models":
            st, _h, body = self.http("GET", "https://models.github.ai/catalog/models",
                                     {"Authorization": f"Bearer {keyv[0]}", **p.get("headers", {})}, None, self.timeout)
            if st != 200 or not isinstance(body, list):
                self.state.setdefault("discover_error", {})[p["name"]] = f"catalog {st}: {str(body)[:120]}"
                return []
            ids = [m.get("id", "") for m in body if isinstance(m, dict) and OPEN_RE.search(m.get("id", ""))
                   and "embed" not in m.get("id", "").lower()]
        elif kind == "openai-models":
            st, _h, body = self.http("GET", p["base"].rstrip("/") + "/models", {"Accept": "application/json"}, None, self.timeout)
            if st != 200 or not isinstance(body, dict):
                self.state.setdefault("discover_error", {})[p["name"]] = f"models {st}: {str(body)[:120]}"
                return []
            ids = [m["id"] for m in body.get("data", []) if isinstance(m, dict) and OPEN_RE.search(m.get("id", ""))
                   and not re.search(r"embed|whisper|tts|speech|bge|image|vision|vl", m.get("id", ""), re.I)]
        elif kind == "pollinations":
            st, _h, body = self.http("GET", "https://text.pollinations.ai/models", {"Accept": "application/json"}, None, self.timeout)
            if st != 200 or not isinstance(body, list):
                self.state.setdefault("discover_error", {})[p["name"]] = f"models {st}: {str(body)[:120]}"
                return []
            ids = [m["name"] for m in body if isinstance(m, dict) and m.get("name")
                   and OPEN_RE.search(m.get("name", "") + " " + m.get("description", "")) and not m.get("audio") and not m.get("tools") is False and "vision" not in str(m.get("description", "")).lower()][:6]
            ids = ids or [m["name"] for m in body if isinstance(m, dict) and OPEN_RE.search(m.get("name", "") + " " + m.get("description", ""))][:6]
        elif kind == "openrouter":
            st, _h, body = self.http("GET", p["base"] + "/models", {"Accept": "application/json"}, None, self.timeout)
            if st != 200 or not isinstance(body, dict):
                self.state.setdefault("discover_error", {})[p["name"]] = f"models {st}: {str(body)[:120]}"
                return []
            ids = [m["id"] for m in body.get("data", []) if str(m.get("pricing", {}).get("prompt", "1")) in ("0", "0.0")
                   and str(m.get("pricing", {}).get("completion", "1")) in ("0", "0.0") and OPEN_RE.search(m["id"])]
        else:
            return []

        def rank(i):
            for n, rx in enumerate(PREFER_RE):
                if rx.search(i):
                    return n
            return 99
        return sorted(ids, key=rank)[:4]

    # ------------------------------------------------------------ calling
    def _endpoint(self, p):
        base = p["base"]
        for k in p.get("keys", []):
            base = base.replace("{" + k + "}", self.env.get(k, ""))
        return base.rstrip("/") + p.get("path", "/chat/completions")

    def _headers(self, p):
        h = {"Content-Type": "application/json", **p.get("headers", {})}
        if p.get("keys"):
            h["Authorization"] = "Bearer " + self.env.get(p.get("token_env", p["keys"][0]), "")
        return h

    def _throttle(self, p):
        if self.cfg.get("no_throttle"):
            return
        gap = 60.0 / max(1, p.get("rpm", 10))
        wait = self.last_call.get(p["name"], 0) + gap - self.now()
        if wait > 0:
            self.sleep(wait)

    def _fail(self, p, why, cool=0):
        st = self._st(p["name"])
        st["fail"] += 1
        st["streak"] += 1
        st["last_error"] = why[:160]
        if cool:
            st["cool"] = self.now() + cool

    def _call(self, p, model, system, user, max_tokens, temperature, json_mode):
        self._throttle(p)
        body = {"model": model, "temperature": temperature, "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        t0 = self.now()
        status, headers, data = self.http("POST", self._endpoint(p), self._headers(p), body, self.timeout)
        self.last_call[p["name"]] = self.now()
        self.calls += 1
        day = self._st(p["name"])["day"]
        if day["d"] != self._today():
            day["d"], day["n"] = self._today(), 0
        day["n"] += 1
        return status, headers, data, int((self.now() - t0) * 1000)

    def _seconds_to_midnight(self):
        n = dt.datetime.fromtimestamp(self.now(), dt.timezone.utc)
        return int((n.replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(days=1) - n).total_seconds()) + 60

    def chat_json(self, task, system, user, required=(), validate=None, max_tokens=700, temperature=0.2, prefer=None, avoid=None):
        key = hashlib.sha256(json.dumps([task, system, user], ensure_ascii=False).encode()).hexdigest()[:24]
        if key in self.cache:
            return self.cache[key]["out"], {"provider": "cache", "model": self.cache[key].get("model", ""), "cached": True,
                                             "source": self.cache[key].get("source", "")}
        errors = []
        for p in self.ordered(prefer, avoid):
            st = self._st(p["name"])
            json_mode = bool(p.get("json")) and st.get("json_ok", True)
            for model in self.models_for(p)[:2]:
                if not self.usable(p):
                    break
                status, headers, data, ms = self._call(p, model, system, user, max_tokens, temperature, json_mode)
                text = ""
                if status == 200 and isinstance(data, dict):
                    try:
                        text = data["choices"][0]["message"]["content"] or ""
                    except Exception:
                        text = ""
                if status == 200 and not text:
                    snip = (data if isinstance(data, str) else json.dumps(data))[:200]
                    st["bad"] += 1
                    st["last_error"] = f"{model}: empty reply {snip}"[:240]
                    errors.append(f"{p['name']}/{model}: empty reply")
                    continue
                if status == 200 and text:
                    obj = extract_json(text)
                    problem = None
                    if obj is None:
                        problem = "reply was not valid JSON"
                    else:
                        miss = [k for k in required if k not in obj]
                        if miss:
                            problem = f"missing keys {miss}"
                        elif validate:
                            try:
                                validate(obj)
                            except ValueError as e:
                                problem = f"rejected: {e}"
                    if problem is None:
                        st["ok"] += 1
                        st["streak"] = 0
                        st["lat"] = int((st["lat"] * (st["ok"] - 1) + ms) / st["ok"]) if st["ok"] else ms
                        st["last_ok"] = dt.datetime.fromtimestamp(self.now(), dt.timezone.utc).isoformat(timespec="seconds")
                        meta = {"provider": p["name"], "model": model, "latency_ms": ms, "cached": False,
                                "source": f"{p['name']}:{model}"}
                        self.cache[key] = {"out": obj, "model": model, "source": meta["source"], "t": self._today()}
                        return obj, meta
                    st["bad"] += 1
                    st["last_error"] = f"{model}: {problem}"[:160]
                    errors.append(f"{p['name']}/{model}: {problem}")
                    continue
                msg = json.dumps(data)[:300].lower() if not isinstance(data, str) else data[:300].lower()
                if status == 429:
                    ra = headers.get("Retry-After") or headers.get("retry-after")
                    quota = any(w in msg for w in ("per day", "daily", "rpd", "quota", "exceeded your"))
                    cool = self._seconds_to_midnight() if quota else (int(ra) if str(ra or "").isdigit() else 120)
                    self._fail(p, "rate limited", cool)
                    errors.append(f"{p['name']}: 429")
                    break
                if status in (401, 403):
                    self._fail(p, f"auth {status}", 3600)
                    self.dead.add(p["name"])
                    errors.append(f"{p['name']}: auth {status}")
                    break
                if status in (400, 422) and json_mode and ("response_format" in msg or "json" in msg):
                    st["json_ok"] = False
                    json_mode = False
                    status, headers, data, ms = self._call(p, model, system, user, max_tokens, temperature, False)
                    if status == 200 and isinstance(data, dict):
                        try:
                            text = data["choices"][0]["message"]["content"] or ""
                        except Exception:
                            text = ""
                        obj = extract_json(text)
                        if obj is not None and not [k for k in required if k not in obj]:
                            try:
                                if validate:
                                    validate(obj)
                                st["ok"] += 1
                                st["streak"] = 0
                                meta = {"provider": p["name"], "model": model, "latency_ms": ms, "cached": False, "source": f"{p['name']}:{model}"}
                                self.cache[key] = {"out": obj, "model": model, "source": meta["source"], "t": self._today()}
                                return obj, meta
                            except ValueError as e:
                                st["bad"] += 1
                                errors.append(f"{p['name']}/{model}: rejected: {e}")
                                continue
                if status in (400, 404, 422):
                    self._fail(p, f"{status} {model}: {msg[:120]}")
                    errors.append(f"{p['name']}/{model}: {status}")
                    continue
                self._fail(p, f"http {status}: {msg[:140]}", 60)
                errors.append(f"{p['name']}: http {status}")
                break
        raise AllFailed("; ".join(errors[-6:]) or "no provider available")

    # ------------------------------------------------------------ persistence
    def trim_cache(self, keep=300):
        if len(self.cache) > keep:
            for k in list(self.cache)[:len(self.cache) - keep]:
                del self.cache[k]
