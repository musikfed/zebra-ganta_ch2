import unittest
from experiment009 import plan, SIZES_KIB, ZONES

class Experiment009Tests(unittest.TestCase):
    def test_unique_nonoverlap_and_balance(self):
        jobs=plan(20261113,12)
        self.assertEqual(len(jobs),5*12*3)
        ranges=sorted((x["offset_bytes"],x["offset_bytes"]+x["read_bytes"]) for x in jobs)
        self.assertTrue(all(a[1]<=b[0] for a,b in zip(ranges,ranges[1:])))
        self.assertTrue(all(x["offset_bytes"]%4096==0 and x["read_bytes"]%4096==0 for x in jobs))
        for z in ZONES:
            for kib in SIZES_KIB:
                self.assertEqual(sum(x["zone_percent"]==z and x["size_kib"]==kib for x in jobs),12)
    def test_reproducible(self):
        self.assertEqual(plan(6,6),plan(6,6))
        self.assertNotEqual(plan(6,6),plan(7,6))
    def test_bounded_sizes(self):
        for n in (-1,0,5,100):
            with self.assertRaises(ValueError):
                plan(6,n)
