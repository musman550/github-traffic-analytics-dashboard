import datetime as dt, json, os, tempfile, unittest
from ghintel.collector import cadence_for, is_due, merge_days
from ghintel.insights import seo_audit

CFG = {"cadence": {"active_days": 1, "idle_days": 3, "dormant_days": 7, "dormant_after_idle_days": 45}}
T = dt.date(2026, 11, 14)


class Cadence(unittest.TestCase):
    def test_active_daily(self):
        st = {"s": "2026-01-01", "a": "2026-11-10", "f": "2026-11-13"}
        self.assertEqual(cadence_for(st, T, CFG), 1)
        self.assertTrue(is_due("r", T, {"r": st}, CFG))

    def test_idle_every_three_days(self):
        st = {"s": "2026-10-20", "f": "2026-11-13"}
        self.assertEqual(cadence_for(st, T, CFG), 3)
        self.assertFalse(is_due("r", T, {"r": st}, CFG))

    def test_dormant_weekly_and_always_within_window(self):
        st = {"s": "2026-01-01", "f": "2026-11-05"}
        self.assertEqual(cadence_for(st, T, CFG), 7)
        self.assertLess(CFG["cadence"]["dormant_days"], 14)  # GitHub keeps a 14-day window

    def test_unknown_repo_and_force(self):
        self.assertTrue(is_due("new", T, {}, CFG))
        self.assertTrue(is_due("r", T, {"r": {"s": "2026-11-14", "f": "2026-11-14"}}, CFG, force=True))


class Merge(unittest.TestCase):
    def test_sparse_upsert(self):
        d = {"2026-11-01": [5, 2]}
        merge_days(d, [{"timestamp": "2026-11-01T00:00:00Z", "count": 0, "uniques": 0},
                       {"timestamp": "2026-11-02T00:00:00Z", "count": 3, "uniques": 1}])
        self.assertEqual(d, {"2026-11-02": [3, 1]})


class Audit(unittest.TestCase):
    def test_scores(self):
        full = {"desc": "A useful description that is long enough to be helpful.", "topics": list("abcdefgh"),
                "license": "MIT", "homepage": "https://x.dev", "pushed": "2026-11-10"}
        self.assertEqual(seo_audit(full, T)["score"], 100)
        empty = {"desc": "", "topics": [], "license": None, "homepage": "", "pushed": "2020-01-01"}
        a = seo_audit(empty, T)
        self.assertEqual(a["score"], 0)
        self.assertTrue(len(a["missing"]) >= 4)


class PrivacyAggregate(unittest.TestCase):
    def test_private_ids_never_reach_summary(self):
        from ghintel import aggregator
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                os.makedirs("docs/data")
                day = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=2)).isoformat()
                json.dump({"repos": {"pub": {"views": {day: [4, 2]}, "clones": {}},
                                     "private-abc123": {"views": {day: [99, 9]}, "clones": {}}}}, open("docs/data/series.json", "w"))
                json.dump([{"id": "pub", "name": "pub", "url": "https://github.com/o/pub", "desc": "d", "topics": [],
                            "lang": None, "license": None, "homepage": "", "stars": 0, "forks": 0, "watchers": 0,
                            "issues": 0, "pushed": day, "created": day, "size": 1, "fork": False, "archived": False}],
                          open("docs/data/repos.json", "w"))
                cfg = {"site_url": "https://x.test/"}
                s = aggregator.build_summary(cfg)
                self.assertEqual(s["totals"]["views_30d"], 4)
                self.assertNotIn("private-abc123", json.dumps(s))
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()


class FakeGH:
    """Stands in for the GitHub client; records every endpoint that is called."""
    def __init__(self, *a, **k):
        FakeGH.calls = []
        self.remaining, self.calls_n = 4000, 0

    @property
    def calls(self):
        return self.calls_n

    def paginate(self, path, params=None):
        return [{"name": n, "full_name": f"o/{n}", "owner": {"login": "o"}, "private": False, "fork": False,
                 "archived": False, "html_url": f"https://github.com/o/{n}", "description": "d", "topics": [],
                 "language": None, "license": None, "homepage": "", "stargazers_count": 0, "forks_count": 0,
                 "watchers_count": 0, "open_issues_count": 0, "pushed_at": "2026-11-10T00:00:00Z",
                 "created_at": "2026-10-01T00:00:00Z", "size": 1, "has_pages": False, "default_branch": "main"}
                for n in ("viewed", "cloneonly", "quiet")] + [{
                 "name": "secret", "full_name": "o/secret", "owner": {"login": "o"}, "private": True, "fork": False,
                 "archived": False, "html_url": "x", "stargazers_count": 0, "forks_count": 0, "watchers_count": 0,
                 "open_issues_count": 0}]

    def get(self, path, params=None, retries=3):
        FakeGH.calls.append(path)
        self.calls_n += 1
        day = "2026-11-10T00:00:00Z"
        if path.endswith("/traffic/views"):
            n = 5 if "/viewed/" in path else 0
            return {"count": n, "uniques": n, "views": [{"timestamp": day, "count": n, "uniques": n}] if n else []}, None
        if path.endswith("/traffic/clones"):
            n = 0 if "/quiet/" in path else 9
            return {"count": n, "uniques": n, "clones": [{"timestamp": day, "count": n, "uniques": n}] if n else []}, None
        if path.endswith("/popular/referrers"):
            return [{"referrer": "google.com", "count": 3, "uniques": 2}], None
        if path.endswith("/popular/paths"):
            return [{"path": "/o/viewed", "title": "t", "count": 3, "uniques": 2}], None
        return None, None

    def text(self, *a, **k):
        return None


class CollectorBehaviour(unittest.TestCase):
    def run_collect(self, today):
        from ghintel import collector
        collector.GH = FakeGH
        os.environ["GHINTEL_TODAY"] = today
        cfg = {"include_forks": False, "include_archived": False, "exclude": [], "min_rate_remaining": 100,
               "sleep_between_calls": 0, "keep_source_days": 90, "cadence": CFG["cadence"]}
        collector.collect(cfg)
        return list(FakeGH.calls)

    def test_private_skipped_referrers_only_for_viewed_and_idle_repos_rest(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                c1 = self.run_collect("2026-11-14")
                self.assertFalse(any("secret" in c for c in c1), "private repo must never be requested")
                self.assertTrue(any("/viewed/traffic/popular/referrers" in c for c in c1))
                self.assertFalse(any("/cloneonly/traffic/popular" in c for c in c1), "clone-only repos need no referrer calls")
                repos = json.load(open("docs/data/repos.json"))
                self.assertEqual({r["id"] for r in repos}, {"viewed", "cloneonly", "quiet"})
                # next day: the viewed repo is fetched again, idle repos wait (staggered up to 3 days)
                c2 = self.run_collect("2026-11-15")
                self.assertTrue(any("/viewed/traffic/views" in c for c in c2))
                idle_calls = [c for c in c2 if "/cloneonly/" in c or "/quiet/" in c]
                self.assertLessEqual(len(idle_calls), 4)
                self.assertNotIn("secret", open("docs/data/series.json").read())
            finally:
                os.environ.pop("GHINTEL_TODAY", None)
                os.chdir(cwd)


class CadencePeriod(unittest.TestCase):
    def test_idle_repo_period_is_stable_three_days(self):
        from ghintel import collector
        cwd = os.getcwd()
        days = []
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                collector.GH = FakeGH
                cfg = {"include_forks": False, "include_archived": False, "exclude": [], "min_rate_remaining": 100,
                       "sleep_between_calls": 0, "keep_source_days": 90, "cadence": CFG["cadence"]}
                for i in range(12):
                    d = (dt.date(2026, 11, 14) + dt.timedelta(days=i)).isoformat()
                    os.environ["GHINTEL_TODAY"] = d
                    collector.collect(cfg)
                    if any("/quiet/traffic/views" in c for c in FakeGH.calls):
                        days.append(dt.date.fromisoformat(d))
            finally:
                os.environ.pop("GHINTEL_TODAY", None)
                os.chdir(cwd)
        gaps = [(b - a).days for a, b in zip(days, days[1:])]
        self.assertLessEqual(max(gaps), 3, gaps)           # never longer than 3 days (safe: window is 14)
        self.assertTrue(all(g == 3 for g in gaps[1:]), gaps)  # stable period after the first spread-out fetch


class Alerts(unittest.TestCase):
    def test_compute_flags_problems_spike_and_digest(self):
        from ghintel import alerts
        daily = [[(dt.date(2026, 9, 1) + dt.timedelta(days=i)).isoformat(), 10 + (i % 3), 0, 0, 0] for i in range(80)]
        daily[-1][1] = 300
        s = {"daily": daily}
        health = {"partial": True, "errors": ["rate guard stop: remaining=399"], "last_run": "2026-11-20T02:50:00+00:00"}
        rep = [{"start": dt.date(2026, 11, 9), "days": [(dt.date(2026, 11, 9) + dt.timedelta(days=i)).isoformat() for i in range(7)],
                "views": 70, "clones": 10, "dv": [10] * 7, "dc": [1] * 7, "repos": {"a": (70, 10)}, "prev": None, "created": 2}]
        titles = [t for t, _ in alerts.compute(s, health, rep, "https://x.test/")]
        self.assertTrue(any(t.startswith("Collection run had problems") for t in titles))
        self.assertTrue(any(t.startswith("Traffic spike on") for t in titles))
        self.assertTrue(any(t.startswith("Weekly report:") for t in titles))

    def test_quiet_when_all_is_well(self):
        from ghintel import alerts
        daily = [[(dt.date(2026, 9, 1) + dt.timedelta(days=i)).isoformat(), 10 + (i % 3), 0, 0, 0] for i in range(80)]
        self.assertEqual(alerts.compute({"daily": daily}, {"partial": False, "errors": [], "last_run": "2026-11-20"}, [], "https://x.test/"), [])

    def test_delivery_is_deduplicated(self):
        from ghintel import alerts, notify
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                os.makedirs("docs/data")
                sent = []
                notify.issue = lambda repo, title, body, labels=("alert",): sent.append(title) or True
                notify.telegram = lambda text: False
                cfg = {"repo_full_name": "o/r", "notifications": {"issues": True, "telegram": True}}
                alerts.deliver(cfg, [("A", "x"), ("B", "y")])
                alerts.deliver(cfg, [("A", "x"), ("C", "z")])
                self.assertEqual(sent, ["A", "B", "C"])
            finally:
                os.chdir(cwd)


class RateBuckets(unittest.TestCase):
    def test_search_bucket_does_not_trip_core_guard(self):
        from ghintel.github_client import GH
        import requests
        g = GH(token="t", min_remaining=400, sleep=0)
        r = requests.Response()
        r.headers.update({"x-ratelimit-remaining": "29", "x-ratelimit-resource": "search", "x-ratelimit-reset": "0"})
        g._note(r)
        self.assertIsNone(g.remaining)
        r.headers.update({"x-ratelimit-remaining": "4500", "x-ratelimit-resource": "core"})
        g._note(r)
        self.assertEqual(g.remaining, 4500)
