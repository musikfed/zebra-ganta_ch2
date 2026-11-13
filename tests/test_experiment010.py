import unittest
from collections import Counter
from experiment010 import schedule,PAUSES,SESSIONS,GAP
from lab import DEFAULT_SIZE
from transitions import BLOCK

class Experiment010Tests(unittest.TestCase):
    def test_schedule_no_repeats(self):
        jobs=schedule()
        self.assertEqual(len(jobs),SESSIONS)
        self.assertEqual(Counter(j["pause_after_open_s"] for j in jobs),{0:3,2:3,10:3})
        addresses=[x for j in jobs for x in (j["first_offset"],j["second_offset"])]
        self.assertEqual(len(addresses),len(set(addresses)))
        self.assertTrue(all(x%BLOCK==0 and 0<x<DEFAULT_SIZE-BLOCK for x in addresses))
        self.assertTrue(all(j["second_offset"]-j["first_offset"]==GAP for j in jobs))
    def test_seed_and_bounds(self):
        self.assertEqual(schedule(3),schedule(3))
        self.assertNotEqual(schedule(3),schedule(4))
        for seed in (-1,2**32):
            with self.assertRaises(ValueError):
                schedule(seed)
