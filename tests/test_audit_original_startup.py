import unittest
from tools.audit_original_startup import report

class OriginalStartupAuditTests(unittest.TestCase):
    def test_archived_runs_and_initial_read_accounting(self):
        r=report()
        self.assertEqual(len(r["startup_samples"]),5)
        self.assertEqual(len(r["exp008_traces"]),4)
        self.assertEqual(r["exp008_traces"][0]["first_read_ms"],356.0742)
        self.assertEqual(r["exp008_by_mode"]["ordered"]["median_full_wall_ms"],1177.6578)
        self.assertTrue(350 < r["startup_min_ms"] < r["startup_max_ms"] < 370)
        self.assertEqual(sum(item["remaining_reads"] for item in r["exp008_traces"]),508)

if __name__=="__main__":unittest.main()
