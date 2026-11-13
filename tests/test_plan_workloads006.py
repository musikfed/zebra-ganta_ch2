"""Pure plan tests for experiment 006: no filesystem or physical HDD I/O."""
import unittest
from tools.plan_workloads006 import TOTAL, SMALL_COUNT, build_workload, describe

class Workloads006Tests(unittest.TestCase):
    def test_one_gib_for_each_scenario(self):
        for scenario,expected in [("single",1024),("small-sequential",4096),("small-interleaved",4096)]:
            rows=build_workload(scenario,4)
            self.assertEqual(len(rows),expected)
            self.assertEqual(sum(r["bytes"] for r in rows),TOTAL)
            self.assertEqual([r["sequence"] for r in rows],list(range(len(rows))))
            self.assertEqual(set(r["stream"] for r in rows),{0,1,2,3})

    def test_deterministic_shuffle_and_digest(self):
        a=describe("small-interleaved",2,13)
        b=describe("small-interleaved",2,13)
        c=describe("small-interleaved",2,14)
        self.assertEqual(a["trace_sha256"],b["trace_sha256"])
        self.assertNotEqual(a["trace_sha256"],c["trace_sha256"])
        self.assertEqual(a["distinct_objects"],SMALL_COUNT)
        self.assertEqual(a["status"],"SYNTHETIC REQUEST PLAN — NO PHYSICAL HDD MEASUREMENTS")

    def test_rejects_unbounded_or_unsupported(self):
        for scenario,streams,seed in [("bad",1,1),("single",3,1),("single",1,-1)]:
            with self.assertRaises(ValueError):
                build_workload(scenario,streams,seed)

if __name__=="__main__":
    unittest.main()
