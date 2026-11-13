"""Experiment 008 pure planning/statistics tests. No devices, files or network."""
import unittest
from argparse import Namespace
from collections import Counter

from experiment008 import (
    ALLOWED_BLOCKS_PER_ZONE, BLOCK, MODES, ROUNDS, SIZE, ZONES,
    build_plan, percentile, summarize, traversal, validate_args,
)


class Experiment008Tests(unittest.TestCase):
    def test_default_plan_unique_and_bounded(self):
        jobs = build_plan()
        per_trial = ZONES * 16
        self.assertEqual(len(jobs), ROUNDS * len(MODES) * per_trial)
        self.assertEqual(len({x["offset_bytes"] for x in jobs}), len(jobs))
        self.assertTrue(all(BLOCK <= x["offset_bytes"] <= SIZE - BLOCK
                            and x["offset_bytes"] % BLOCK == 0 for x in jobs))
        for rnd in range(1, ROUNDS+1):
            trials = [(x["slot"], x["mode"]) for x in jobs if x["round"] == rnd]
            self.assertEqual(
                sorted(set(trials)),
                sorted(enumerate(MODES[rnd-1:] + MODES[:rnd-1], 1)))
            for mode in MODES:
                subset = [x for x in jobs if x["round"] == rnd and x["mode"] == mode]
                self.assertEqual(len(subset), per_trial)
                self.assertEqual(Counter(x["zone"] for x in subset),
                                 {z: 16 for z in range(1, ZONES+1)})
                self.assertIsNone(subset[0]["distance_from_previous_bytes"])
                self.assertEqual([x["step"] for x in subset], list(range(1, per_trial+1)))

    def test_determinism_and_safe_bounds(self):
        self.assertEqual(build_plan(8, 21), build_plan(8, 21))
        self.assertNotEqual(build_plan(8, 21), build_plan(8, 22))
        for n in ALLOWED_BLOCKS_PER_ZONE:
            self.assertEqual(len(build_plan(n)), ROUNDS*len(MODES)*ZONES*n)
        for n in (0, 2, 7, 33, 64):
            with self.assertRaises(ValueError):
                build_plan(n)
        for seed in (-1, 2**32):
            with self.assertRaises(ValueError):
                build_plan(8, seed)

    def test_traversals_same_address_set_different_order(self):
        addresses = [(n*BLOCK, 1) for n in range(1, 17)]
        seq = traversal(addresses, "sequential", 17)
        alt = traversal(addresses, "alternating", 17)
        random_order = traversal(addresses, "shuffled", 17)
        self.assertEqual(set(seq), set(alt))
        self.assertEqual(set(seq), set(random_order))
        self.assertNotEqual(seq, alt)
        self.assertEqual(random_order, traversal(addresses, "shuffled", 17))
        with self.assertRaises(ValueError):
            traversal(addresses, "bad", 17)

    def test_locked_disk_identity(self):
        baseline = dict(disk=2, letter="T", size=SIZE, win32_size=500105249280,
                        bridge="usb3-orico", vidpid="2109:0715", link_speed="Super",
                        blocks_per_zone=16, seed=20261113)
        validate_args(Namespace(**baseline))
        for key, bad in (("disk", 0), ("letter", "D"), ("size", SIZE-1),
                         ("win32_size", 0), ("bridge", "usb2-jmicron"),
                         ("vidpid", "152D:2338"), ("link_speed", "High"),
                         ("blocks_per_zone", 100), ("seed", -1)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_args(Namespace(**{**baseline, key: bad}))

    def test_percentiles(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], .5), 3)
        self.assertAlmostEqual(percentile([1, 2, 3, 4, 5], .95), 4.8)
        for values, q in (([], 0.5), ([1,2], -0.1), ([1,2], 1.1)):
            with self.assertRaises(ValueError):
                percentile(values, q)

    def test_summary_calculates_real_timing_not_plan(self):
        source = build_plan(8, 12)
        observed = [{**x, "read_ms": 8.0 if x["mode"] == "sequential"
                     else 16.0} for x in source]
        durations = {(r, mode): (100.0 if mode == "sequential" else 200.0)
                     for r in range(1, ROUNDS+1) for mode in MODES}
        report = summarize(observed, durations, 8)
        self.assertEqual(len(report), ROUNDS * len(MODES))
        self.assertEqual(next(x for x in report if x["mode"] == "alternating")[
            "elapsed_vs_sequential_percent"], 100.0)
        self.assertEqual(next(x for x in report if x["mode"] == "sequential")[
            "p95_read_ms"], 8.0)
        with self.assertRaises(ValueError):
            summarize(observed[:-1], durations, 8)
        with self.assertRaises(ValueError):
            summarize(observed, {(1, "sequential"): 100.0}, 8)
        observed[-1]["offset_bytes"] = observed[0]["offset_bytes"]
        with self.assertRaises(ValueError):
            summarize(observed, durations, 8)


if __name__ == "__main__":
    unittest.main()
