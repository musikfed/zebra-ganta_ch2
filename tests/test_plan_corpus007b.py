"""Tests for pure corpus planning, without any filesystem I/O."""
import unittest
from tools.plan_corpus007b import GIB, SMALL_COUNT, SMALL_FILE_BYTES, make_plan

class Corpus007BTests(unittest.TestCase):
    def test_equal_useful_bytes(self):
        p = make_plan("separate-test-volume")
        self.assertEqual(p["variants"][0]["useful_bytes"], GIB)
        self.assertEqual(p["variants"][1]["useful_bytes"], GIB)
        self.assertEqual(SMALL_COUNT * SMALL_FILE_BYTES, GIB)
        self.assertEqual(p["minimum_prudent_free_space_bytes"], 4 * GIB)

    def test_no_approval_even_when_hgst_selected(self):
        p = make_plan("hgst-t")
        self.assertFalse(p["target_approved_for_writes"])
        self.assertFalse(p["generator_implemented"])
        self.assertFalse(p["physical_access"])
        self.assertEqual(p["status"], "PLAN_ONLY_NO_DISK_IO")

    def test_archive_unknown_and_optional(self):
        self.assertIn("UNKNOWN", make_plan("separate-test-volume")["variants"][2]["archive_bytes"])
        self.assertEqual(len(make_plan("separate-test-volume", False)["variants"]), 2)

    def test_invalid_target(self):
        with self.assertRaises(ValueError):
            make_plan("C:")

if __name__ == "__main__":
    unittest.main()
