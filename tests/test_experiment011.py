import unittest
from collections import Counter
from experiment011 import plan, PAUSES, REPETITIONS, OFFSET_GAP
from lab import DEFAULT_SIZE
from transitions import BLOCK

class Experiment011PlanTests(unittest.TestCase):
    def test_balanced_disjoint_read_only_plan(self):
        jobs=plan()
        self.assertEqual(len(jobs),len(PAUSES)*REPETITIONS)
        self.assertEqual(Counter(x["pause_after_open_s"] for x in jobs),
                         {p:REPETITIONS for p in PAUSES})
        offsets=[offset for j in jobs for offset in (j["first_offset"],j["second_offset"])]
        self.assertEqual(len(offsets),len(set(offsets)))
        self.assertTrue(all(x>0 and x%BLOCK==0 and x+BLOCK<=DEFAULT_SIZE for x in offsets))
        self.assertTrue(all(j["second_offset"]-j["first_offset"]==OFFSET_GAP for j in jobs))
    def test_deterministic_and_bounded(self):
        self.assertEqual(plan(101),plan(101))
        self.assertNotEqual(plan(101),plan(102))
        for seed in (-1,2**32,1.5):
            with self.assertRaises(ValueError):plan(seed)
