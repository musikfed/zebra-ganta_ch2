import tempfile
import unittest
from pathlib import Path

from analyze_transitions import summarize


class TransitionAnalysisTests(unittest.TestCase):
    def test_actual_pairing_not_difference_of_medians(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/"observations.csv"
            p.write_text("pair,mode,target_read_ms\n1,near,1\n1,far,10\n2,near,2\n2,far,4\n3,near,100\n3,far,5\n",encoding="utf-8")
            s = summarize(p)
            self.assertEqual(s["pairs"],3)
            self.assertEqual(s["near_median_ms"],2)
            self.assertEqual(s["far_median_ms"],5)
            self.assertEqual(s["difference_of_medians_ms"],3)
            self.assertEqual(s["median_of_paired_differences_ms"],2)

    def test_incomplete_pairs_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"observations.csv"
            p.write_text("pair,mode,target_read_ms\n1,near,2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                summarize(p)


if __name__=="__main__":
    unittest.main()
