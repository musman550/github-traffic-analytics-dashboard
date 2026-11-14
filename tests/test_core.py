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
