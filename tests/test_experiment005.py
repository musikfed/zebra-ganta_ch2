"""Unit tests for exp005 plan. Never access actual devices."""
import unittest

from experiment005 import ROUNDS, schedule, validate_args
from lab import DEFAULT_SIZE
from transitions import BLOCK, MIN_GAP


class Experiment005Tests(unittest.TestCase):
    def test_default_plan_160_target_operations(self):
        rows = schedule(20, 20261115)
        self.assertEqual(len(rows), 160)
        for pair in range(1,21):
            selected=[r for r in rows if r["pair"]==pair]
            self.assertEqual(len(selected), 8)
            for r in range(1,5):
                modes=[x["mode"] for x in selected if x["round"]==r]
                self.assertEqual(tuple(modes),ROUNDS[r-1])
            self.assertEqual(len({x["anchor_offset"] for x in selected}),1)
            self.assertEqual(len({x["target_offset"] for x in selected}),2)
            self.assertTrue(all(x["target_offset"]%BLOCK==0 for x in selected))
            self.assertTrue(all(x["distance_bytes"] in
                (MIN_GAP, selected[1]["distance_bytes"]) for x in selected))

    def test_seed_deterministic_and_40_pairs_bounded(self):
        self.assertEqual(schedule(20,17),schedule(20,17))
        self.assertNotEqual(schedule(20,17),schedule(20,18))
        self.assertEqual(len(schedule(40,5)),320)
        for n in (0,4,19,41,200):
            with self.assertRaises(ValueError):
                schedule(n,1)

    def test_invalid_args_rejected_without_disk_open(self):
        from argparse import Namespace
        base=dict(disk=2,letter="T",size=DEFAULT_SIZE,win32_size=500105249280,
                  bridge="usb3-orico",vidpid="2109:0715",link_speed="Super",pairs=20)
        validate_args(Namespace(**base))
        for name,bad in [("letter","C"),("size",999),("bridge","usb2-jmicron"),
                         ("vidpid","152D:2338"),("win32_size",0),
                         ("link_speed","High"),("pairs",200)]:
            values={**base,name:bad}
            with self.assertRaises(RuntimeError):
                validate_args(Namespace(**values))


if __name__=="__main__":
    unittest.main()
