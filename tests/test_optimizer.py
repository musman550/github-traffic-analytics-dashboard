import datetime as dt, json, os, tempfile, unittest
from unittest import mock
from ghintel.ai.router import AllFailed, Router, extract_json
from ghintel.optimizer import apply as A, evaluate as E, generate as G, select as S

OCFG = {"enabled": True, "max_repos_per_run": 10, "cooldown_days": 21, "evaluate_after_days": 14, "min_baseline_views": 20,
        "drop_threshold": 0.3, "auto_merge_days": 3, "readme_declined_cooldown_days": 90,
        "exclude": ["profile-repo"], "generated_prefixes": ["bot-"], "generated_readme": False,
        "description_policy": "improve_if_weak", "max_topics": 12, "branch_prefix": "auto-seo/",
        "block_start": "<!-- AUTO-SEO:START -->", "block_end": "<!-- AUTO-SEO:END -->", "use_judge": True}
CFG = {"optimizer": OCFG, "ai": {"no_throttle": True, "anon_enabled": False, "order": ["groq", "cerebras", "mistral", "gemini"]}, "min_rate_remaining": 10,
       "site_url": "https://x.test/", "repo_full_name": "o/r"}
README = ("# Weather Bot\n\nA small Python service that posts daily weather summaries to Telegram using the OpenWeather API. "
          "It runs with Docker and supports 3 cities.\n\n## Usage\n\nSet your Telegram bot token first, then run `docker compose up`.\n")
CTX = {"name": "weather-bot", "full": "o/weather-bot", "desc": "", "topics": ["python"], "lang": "Python", "files": ["Dockerfile", "README.md"],
       "readme": README, "readme_raw": README, "has_readme": True, "branch": "main"}
GOOD = {"description": "Python weather bot that posts daily summaries to Telegram", "topics": ["telegram-bot", "docker", "weather"],
        "summary": "A Python service that posts daily weather summaries to Telegram.", "faq": [{"q": "How do I run it?", "a": "Run docker compose up."}]}


def resp(obj):
    return 200, {}, {"choices": [{"message": {"content": json.dumps(obj)}}]}


class FakeHTTP:
    def __init__(self, script):
        self.script, self.calls = script, []

    def __call__(self, method, url, headers, body=None, timeout=45):
        host = url.split("/")[2]
        self.calls.append((host, (body or {}).get("model"), "response_format" in (body or {})))
        r = self.script[host]
        r = r.pop(0) if isinstance(r, list) else r
        return r(body) if callable(r) else r


class RouterTests(unittest.TestCase):
    def router(self, script, env=None, cfg=None):
        env = {"GROQ_API_KEY": "k", "CEREBRAS_API_KEY": "k", "MISTRAL_API_KEY": "k"} if env is None else env
        self.h = FakeHTTP(script)
        return Router(cfg or CFG, {}, {}, http=self.h, env=env, sleep=lambda s: None)

    def test_falls_through_rate_limit_then_bad_json_to_working_provider(self):
        r = self.router({"api.groq.com": (429, {"Retry-After": "30"}, {"error": "slow down"}),
                         "api.cerebras.ai": (200, {}, {"choices": [{"message": {"content": "sorry, no JSON"}}]}),
                         "api.mistral.ai": resp(GOOD)})
        out, meta = r.chat_json("t", "s", "u", required=("description",))
        self.assertEqual(meta["provider"], "mistral")
        st = r.status()
        self.assertTrue(next(p for p in st if p["name"] == "groq")["cooldown"])
        self.assertGreaterEqual(next(p for p in st if p["name"] == "cerebras")["bad"], 1)

    def test_cache_and_persisted_cooldown(self):
        r = self.router({"api.groq.com": resp(GOOD)}, env={"GROQ_API_KEY": "k"})
        r.chat_json("t", "s", "u")
        n = len(self.h.calls)
        _, meta = r.chat_json("t", "s", "u")
        self.assertTrue(meta["cached"])
        self.assertEqual(len(self.h.calls), n)

    def test_no_keys_means_all_failed_and_closed_models_excluded(self):
        with self.assertRaises(AllFailed):
            self.router({}, env={}).chat_json("t", "s", "u")
        r = self.router({"generativelanguage.googleapis.com": resp(GOOD)}, env={"GEMINI_API_KEY": "k"})
        with self.assertRaises(AllFailed):  # closed model provider is off by default
            r.chat_json("t", "s", "u")

    def test_auth_failure_disables_provider_for_run(self):
        r = self.router({"api.groq.com": (401, {}, {"error": "bad key"}), "api.cerebras.ai": resp(GOOD)})
        _, meta = r.chat_json("t", "s", "u")
        self.assertEqual(meta["provider"], "cerebras")
        self.assertIn("groq", r.dead)

    def test_json_mode_rejection_retries_without_it(self):
        def groq(body):
            return (400, {}, {"error": "response_format json not supported"}) if "response_format" in body else resp(GOOD)
        r = self.router({"api.groq.com": groq}, env={"GROQ_API_KEY": "k"})
        _, meta = r.chat_json("t", "s", "u")
        self.assertEqual(meta["provider"], "groq")
        self.assertFalse(r._st("groq")["json_ok"])

    def test_daily_cap_skips_provider(self):
        cfg = {**CFG, "ai": {**CFG["ai"], "providers": {"groq": {"daily": 1}}}}
        r = self.router({"api.groq.com": resp(GOOD), "api.cerebras.ai": resp(GOOD)}, cfg=cfg)
        r.chat_json("a", "s", "u1")
        _, meta = r.chat_json("b", "s", "u2")
        self.assertEqual(meta["provider"], "cerebras")

    def test_extract_json_tolerates_fences_and_chatter(self):
        self.assertEqual(extract_json("```json\n{\"a\": 1}\n```"), {"a": 1})
        self.assertEqual(extract_json("Sure! {\"a\": 2} hope it helps"), {"a": 2})
        self.assertIsNone(extract_json("no json here"))


class ValidationTests(unittest.TestCase):
    def test_good_proposal_passes(self):
        G.validate(dict(GOOD), CTX)

    def test_rejects_hype_ungrounded_topics_bad_length_and_invented_numbers(self):
        for bad in ({**GOOD, "description": "The best ultimate weather bot ever made, guaranteed to work"},
                    {**GOOD, "topics": ["blockchain"]},
                    {**GOOD, "description": "short"},
                    {**GOOD, "faq": [{"q": "How many cities?", "a": "It supports 250 cities worldwide."}]},
                    {**GOOD, "summary": "See https://evil.example for more"}):
            with self.assertRaises(ValueError, msg=str(bad)):
                G.validate(bad, CTX)

    def test_rules_fallback_is_grounded_and_improves_weak_description(self):
        p = G.rule_proposal(CTX)
        G.validate(p, CTX)
        self.assertIn("telegram-bot", p["topics"])
        self.assertIn("docker", p["topics"])
        self.assertTrue(p.get("description", "").startswith("A small Python service"))
        self.assertNotIn("python", p["topics"])  # already present

    def test_propose_uses_rules_when_ai_unavailable_and_when_judge_rejects(self):
        r = Router(CFG, {}, {}, http=FakeHTTP({}), env={}, sleep=lambda s: None)
        p, notes = G.propose(r, CTX, True)
        self.assertEqual(p["source"], "rules")
        h = FakeHTTP({"api.groq.com": [resp(GOOD), resp({"faithful": False, "unsupported": ["claims Telegram"]})]})
        r2 = Router(CFG, {}, {}, http=h, env={"GROQ_API_KEY": "k"}, sleep=lambda s: None)
        p2, n2 = G.propose(r2, CTX, True)
        self.assertEqual(p2["source"], "rules")
        self.assertTrue(any("judge rejected" in n for n in n2))


class RuleQualityTests(unittest.TestCase):
    NEWS = ("# Some AI News Item\n\n> Curated, written, and published by **Acme AI**.\n\n## Overview\n\n"
            "This week, Copilot comes to JetBrains and Xcode with updates for pull requests, settings, and agent sessions across teams. More follows.\n")

    def test_boilerplate_is_skipped_and_overview_preferred(self):
        d = G.first_sentence(self.NEWS)
        self.assertTrue(d.startswith("This week, Copilot comes to JetBrains and Xcode"), d)
        self.assertNotIn("Curated", d)
        self.assertLessEqual(len(d), 160)

    def test_cut_happens_at_natural_boundary(self):
        s = "MCP server for Musfiraai, request free custom tools, automations, AI agents, and n8n workflows directly from Claude Desktop, Claude Code, or any compatible client"
        out = G.smart_cut(s, 160)
        self.assertLessEqual(len(out), 160)
        self.assertFalse(out.endswith((" or any", " or", ",")))
        self.assertEqual(G.smart_cut("short text", 160), "short text")

    def test_weak_topics_need_repeated_evidence(self):
        ctx = {**CTX, "readme": "# X\n\nA tool. Subscribe on YouTube once.\n", "readme_raw": "", "topics": [], "name": "x-tool"}
        self.assertNotIn("youtube", G.rule_proposal(ctx)["topics"])

    def test_junk_topics_removed_real_topics_kept(self):
        ctx = {**CTX, "topics": ["a", "of", "5", "ollama", "n8n"], "desc": "A decent description that is already good enough here."}
        ch = A.metadata_changes(ctx, {"topics": []}, [], OCFG)
        self.assertEqual(ch["topics"]["after"], ["ollama", "n8n"])
        self.assertEqual(ch["topics"]["removed"], ["a", "of", "5"])


class ApplyTests(unittest.TestCase):
    def test_block_is_idempotent_and_preserves_original(self):
        block = OCFG["block_start"] + "\n> **Summary:** x\n" + OCFG["block_end"]
        once = A.upsert_block(README, block, OCFG["block_start"], OCFG["block_end"])
        twice = A.upsert_block(once, block, OCFG["block_start"], OCFG["block_end"])
        self.assertEqual(once, twice)
        self.assertTrue(once.startswith("# Weather Bot\n\n" + OCFG["block_start"]))
        self.assertIn("then run `docker compose up`.", once)
        newer = block.replace("x", "y")
        self.assertEqual(A.upsert_block(once, newer, OCFG["block_start"], OCFG["block_end"]).count(OCFG["block_start"]), 1)

    def test_topics_are_only_added_never_removed_and_capped(self):
        self.assertEqual(A.merge_topics(["a", "b"], ["b", "c"], 12), ["a", "b", "c"])
        self.assertEqual(len(A.merge_topics([str(i) for i in range(11)], ["x", "y", "z"], 12)), 12)
        ch = A.metadata_changes({**CTX, "desc": "A decent description that is already good enough here."}, GOOD, ["docker"], OCFG)
        self.assertNotIn("description", ch)  # good descriptions are left alone
        self.assertEqual(ch["topics"]["after"], ["python", "docker"])

    def test_block_needs_real_content(self):
        self.assertEqual(A.build_block(CTX, {"summary": "", "faq": []}, ["a"], [], "", OCFG, "https://x.test/"), "")


class SelectEvaluateTests(unittest.TestCase):
    def repo(self, name, score=50, tier="mid", v30=0, fork=False):
        return {"name": name, "audit": {"score": score}, "tier": tier, "v30": v30, "fork": fork, "archived": False}

    def test_exclusions_cooldown_and_priority(self):
        today = dt.date(2026, 11, 20)
        repos = [self.repo("profile-repo"), self.repo("tool-a", 10), self.repo("bot-news", 10), self.repo("tool-b", 90), self.repo("fork", 0, fork=True), self.repo("tool-c", 10)]
        log = [{"repo": "tool-c", "mode": "live", "date": "2026-11-10"}, {"repo": "tool-b", "mode": "dry", "date": "2026-11-19"}]
        names = [n for _, n, _, _ in S.select({"optimizer": OCFG}, repos, log, today)]
        self.assertNotIn("profile-repo", names)
        self.assertNotIn("fork", names)
        self.assertNotIn("tool-c", names)  # touched 10 days ago (live) -> cooling down
        self.assertIn("tool-b", names)     # dry runs do not start a cooldown
        self.assertLess(names.index("tool-a"), names.index("bot-news"))  # product outranks generated
        self.assertEqual(S.classify("bot-news", OCFG), "generated")

    def test_rule_only_work_is_revisited_sooner_than_ai_work(self):
        today = dt.date(2026, 11, 20)
        repos = [self.repo("tool-a", 10), self.repo("tool-b", 10)]
        log = [{"repo": "tool-a", "mode": "live", "date": "2026-11-15", "source": "rules"},
               {"repo": "tool-b", "mode": "live", "date": "2026-11-15", "source": "ai:groq:x"}]
        names = [n for _, n, _, _ in S.select({"optimizer": {**OCFG, "rules_cooldown_days": 3}}, repos, log, today)]
        self.assertEqual(names, ["tool-a"])

    def test_rollback_only_with_clear_drop_and_enough_traffic(self):
        class GW:
            def __init__(s): s.sent = []
            def send(s, m, p, b=None): s.sent.append((m, p, b)); return 200, {}
        d0 = dt.date(2026, 11, 1)
        series = {"drop": {"views": {}}, "quiet": {"views": {}}, "fine": {"views": {}}}
        for i in range(1, 15):
            series["drop"]["views"][(d0 - dt.timedelta(days=i)).isoformat()] = [10, 1]
            series["fine"]["views"][(d0 - dt.timedelta(days=i)).isoformat()] = [10, 1]
            series["fine"]["views"][(d0 + dt.timedelta(days=i)).isoformat()] = [10, 1]
            series["quiet"]["views"][(d0 - dt.timedelta(days=i)).isoformat()] = [1, 1]
        mk = lambda n: {"repo": n, "owner": "o", "mode": "live", "status": "applied", "date": d0.isoformat(),
                        "changes": {"description": {"before": "old", "after": "new"}, "topics": {"before": ["a"], "after": ["a", "b"]}}}
        log = [mk("drop"), mk("quiet"), mk("fine")]
        gw = GW()
        E.evaluate_changes(gw, log, series, OCFG, dt.date(2026, 11, 20))
        by = {e["repo"]: e["status"] for e in log}
        self.assertEqual(by, {"drop": "reverted", "quiet": "kept", "fine": "kept"})
        self.assertEqual([(m, p) for m, p, _ in gw.sent], [("PATCH", "/repos/o/drop"), ("PUT", "/repos/o/drop/topics")])
        self.assertEqual(gw.sent[0][2], {"description": "old"})

    def test_pr_follow_up_merge_and_decline(self):
        class GW:
            def __init__(s, data): s.data, s.sent = data, []
            def get(s, path, params=None): return s.data[path], None
            def send(s, m, p, b=None): s.sent.append((m, p)); return 200, {}
        log = [{"repo": "a", "mode": "live", "readme": {"repo": "o/a", "number": 1, "status": "pending", "opened": "2026-11-10"}},
               {"repo": "b", "mode": "live", "readme": {"repo": "o/b", "number": 2, "status": "pending", "opened": "2026-11-10"}},
               {"repo": "c", "mode": "live", "readme": {"repo": "o/c", "number": 3, "status": "pending", "opened": "2026-11-19"}}]
        gw = GW({"/repos/o/a/pulls/1": {"state": "open", "mergeable": True}, "/repos/o/b/pulls/2": {"state": "closed", "merged": False},
                 "/repos/o/c/pulls/3": {"state": "open", "mergeable": True}})
        E.refresh_prs(gw, log, OCFG, dt.date(2026, 11, 20))
        self.assertEqual([e["readme"]["status"] for e in log], ["merged", "declined", "pending"])
        self.assertEqual(gw.sent, [("PUT", "/repos/o/a/pulls/1/merge")])
        self.assertTrue(S.readme_declined([{"repo": "b", "mode": "live", "date": "2026-11-10", "readme": log[1]["readme"]}], "b", dt.date(2026, 11, 20), 90))


class FakeGH:
    def __init__(self, *a, **k):
        FakeGH.sent = []
        self.calls, self.remaining = 0, 4000

    def get(self, path, params=None, retries=3):
        self.calls += 1
        if path.endswith("/contents/"):
            return [{"name": "Dockerfile"}, {"name": "README.md"}], None
        if path.endswith("/readme"):
            return {"path": "README.md", "sha": "blob1"}, None
        if "/git/ref/heads/" in path:
            return {"object": {"sha": "sha1"}}, None
        if path == "/search/repositories":
            return {"total_count": 1200}, None
        return None, None

    def text(self, path, accept=None):
        return README

    def send(self, method, path, body=None, retries=2):
        FakeGH.sent.append((method, path, body))
        if path.endswith("/pulls"):
            return 201, {"number": 7, "html_url": "https://github.com/o/weather-bot/pull/7"}
        return 200 if method != "POST" else 201, {}


class RunIntegration(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        os.makedirs("docs/data")
        meta = lambda n, d: {"id": n, "name": n, "url": f"https://github.com/o/{n}", "desc": d, "topics": ["python"] if n == "weather-bot" else [],
                             "lang": "Python", "license": None, "homepage": "", "stars": 0, "forks": 0, "pushed": "2026-11-10", "created": "2026-10-01",
                             "fork": False, "archived": False, "branch": "main", "size": 1, "issues": 0, "watchers": 0}
        rep = lambda n: {"name": n, "url": f"https://github.com/o/{n}", "desc": "", "topics": ["python"], "fork": False, "archived": False,
                         "audit": {"score": 20}, "tier": "mid", "v30": 0}
        json.dump([meta("weather-bot", ""), meta("profile-repo", "x")], open("docs/data/repos.json", "w"))
        json.dump({"repos": [rep("weather-bot"), rep("profile-repo")]}, open("docs/data/summary.json", "w"))
        json.dump({"login": "o", "links": [{"url": "https://site.test", "kind": "website"}]}, open("docs/data/profile.json", "w"))
        json.dump({"repos": {}}, open("docs/data/series.json", "w"))
        os.environ.update({"GROQ_API_KEY": "k", "GHINTEL_TODAY": "2026-11-20"})

    def tearDown(self):
        os.chdir(self.cwd)
        for k in ("GROQ_API_KEY", "GHINTEL_TODAY"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def run_opt(self, dry):
        from ghintel.optimizer import run as R
        h = FakeHTTP({"api.groq.com": [resp(GOOD), resp({"faithful": True, "unsupported": []})]})
        cfg = json.loads(json.dumps(CFG)); cfg["ai"]["order"] = ["groq"]
        with mock.patch.object(R, "GH", FakeGH), mock.patch("ghintel.ai.router.http_json", h), mock.patch("time.sleep", lambda s: None):
            return R.run(cfg, dry=dry), h

    def test_dry_run_changes_nothing_but_logs_a_proposal(self):
        counts, _ = self.run_opt(True)
        self.assertEqual(FakeGH.sent, [])
        log = json.load(open("docs/data/optimizer_log.json"))
        self.assertEqual([e["repo"] for e in log], ["weather-bot"])  # excluded repo never touched
        self.assertEqual(log[0]["status"], "dry_run")
        self.assertIn("telegram-bot", log[0]["changes"]["topics"]["after"])
        self.assertTrue(log[0]["readme"]["preview"].startswith("<!-- AUTO-SEO:START -->"))

    def test_live_run_updates_metadata_opens_pr_and_logs(self):
        counts, _ = self.run_opt(False)
        methods = [(m, p) for m, p, _ in FakeGH.sent]
        self.assertIn(("PATCH", "/repos/o/weather-bot"), methods)
        topics_call = next(b for m, p, b in FakeGH.sent if p.endswith("/topics"))
        self.assertEqual(topics_call["names"][0], "python")  # existing topic kept, new ones appended
        self.assertIn(("POST", "/repos/o/weather-bot/git/refs"), methods)
        self.assertIn(("POST", "/repos/o/weather-bot/pulls"), methods)
        self.assertFalse(any("profile-repo" in p for _, p, _ in FakeGH.sent))
        log = json.load(open("docs/data/optimizer_log.json"))
        self.assertEqual(log[0]["status"], "applied")
        self.assertEqual(log[0]["readme"]["status"], "pending")
        self.assertEqual(json.load(open("docs/data/optimizer_state.json"))["mode"], "live")
        self.assertTrue(os.path.exists("docs/data/ai_state.json"))


if __name__ == "__main__":
    unittest.main()


class AnonProviders(unittest.TestCase):
    def test_keyless_provider_works_without_authorization_header_and_with_discovery(self):
        seen = []

        def http(method, url, headers, body=None, timeout=45):
            seen.append((method, url, "Authorization" in headers))
            if url.endswith("/models"):
                return 200, {}, {"data": [{"id": "Meta-Llama-3_3-70B-Instruct"}, {"id": "bge-multilingual-gemma2"}, {"id": "gpt-4o"}]}
            return resp(GOOD)
        cfg = {**CFG, "ai": {**CFG["ai"], "order": ["ovhcloud"], "anon_enabled": True}}
        r = Router(cfg, {}, {}, http=http, env={}, sleep=lambda s: None)
        _, meta = r.chat_json("t", "s", "u")
        self.assertEqual(meta["provider"], "ovhcloud")
        self.assertEqual(meta["model"], "Meta-Llama-3_3-70B-Instruct")
        self.assertFalse(any(a for _, _, a in seen))


class RouterRobustness(unittest.TestCase):
    def test_empty_200_reply_tries_next_model_instead_of_benching_provider(self):
        calls = []

        def groq(body):
            calls.append(body["model"])
            if body["model"] == "openai/gpt-oss-120b":
                return 200, {}, {"choices": [{"message": {"content": None}, "finish_reason": "length"}]}
            return resp(GOOD)
        h = FakeHTTP({"api.groq.com": groq})
        r = Router(CFG, {}, {}, http=h, env={"GROQ_API_KEY": "k"}, sleep=lambda s: None)
        _, meta = r.chat_json("t", "s", "u")
        self.assertEqual(meta["provider"], "groq")
        self.assertEqual(calls[:2], ["openai/gpt-oss-120b", "llama-3.3-70b-versatile"])
        self.assertFalse(r.status()[0]["cooldown"])

    def test_error_body_snippet_is_kept_for_diagnosis(self):
        h = FakeHTTP({"api.groq.com": (500, {}, {"error": "upstream exploded"})})
        r = Router(CFG, {}, {}, http=h, env={"GROQ_API_KEY": "k"}, sleep=lambda s: None)
        with self.assertRaises(AllFailed):
            r.chat_json("t", "s", "u")
        self.assertIn("upstream exploded", r.status()[0]["last_error"])

    def test_probe_reports_each_provider(self):
        from ghintel.ai import probe as P
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                os.makedirs("docs/data")
                os.environ["GROQ_API_KEY"] = "k"
                with mock.patch("ghintel.ai.router.http_json", FakeHTTP({"api.groq.com": resp({"ok": True})})):
                    out = P.probe({**CFG, "ai": {**CFG["ai"], "order": ["groq", "cerebras"]}})
            finally:
                os.environ.pop("GROQ_API_KEY", None)
                os.chdir(cwd)
        by = {p["name"]: p for p in out["providers"]}
        self.assertEqual(by["groq"]["tests"][0]["status"], 200)
        self.assertEqual(by["cerebras"]["skipped"], "no key configured")
