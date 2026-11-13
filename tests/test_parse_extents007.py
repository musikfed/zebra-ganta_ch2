import unittest
from tools.parse_extents007 import parse_extents

class ParseExtentMapTests(unittest.TestCase):
    # Captured VCN, length, LCN digits from Acer D:\msdia80.dll, 13 Nov 2026
    RAW = b"""
VCN: 0x0   LENGTH: 0x6   LCN: 0x1d52cd
VCN: 0x6   LENGTH: 0xa   LCN: 0xffffffffffffffff
VCN: 0x10  LENGTH: 0x8   LCN: 0x1d52d3
VCN: 0x18  LENGTH: 0x8   LCN: 0xffffffffffffffff
VCN: 0x20  LENGTH: 0x9   LCN: 0x1d52db
VCN: 0x29  LENGTH: 0x7   LCN: 0xffffffffffffffff
VCN: 0x30  LENGTH: 0xb   LCN: 0x1d52e4
VCN: 0x3b  LENGTH: 0x5   LCN: 0xffffffffffffffff
VCN: 0x40  LENGTH: 0xb   LCN: 0x1d52ef
VCN: 0x4b  LENGTH: 0x5   LCN: 0xffffffffffffffff
VCN: 0x50  LENGTH: 0xc   LCN: 0x1d52fa
VCN: 0x5c  LENGTH: 0x4   LCN: 0xffffffffffffffff
VCN: 0x60  LENGTH: 0xb   LCN: 0x1d5306
VCN: 0x6b  LENGTH: 0x5   LCN: 0xffffffffffffffff
VCN: 0x70  LENGTH: 0xc   LCN: 0x1d5311
VCN: 0x7c  LENGTH: 0x4   LCN: 0xffffffffffffffff
VCN: 0x80  LENGTH: 0xc   LCN: 0x1d531d
VCN: 0x8c  LENGTH: 0x4   LCN: 0xffffffffffffffff
VCN: 0x90  LENGTH: 0xd   LCN: 0x1d5329
VCN: 0x9d  LENGTH: 0x3   LCN: 0xffffffffffffffff
VCN: 0xa0  LENGTH: 0xc   LCN: 0x1d5336
VCN: 0xac  LENGTH: 0x4   LCN: 0xffffffffffffffff
VCN: 0xb0  LENGTH: 0xa   LCN: 0x1d5342
VCN: 0xba  LENGTH: 0x6   LCN: 0xffffffffffffffff
VCN: 0xc0  LENGTH: 0xa   LCN: 0x1d534c
VCN: 0xca  LENGTH: 0x6   LCN: 0xffffffffffffffff
VCN: 0xd0  LENGTH: 0x6   LCN: 0x1d5356
VCN: 0xd6  LENGTH: 0xa   LCN: 0xffffffffffffffff
"""

    def test_captured_case(self):
        r=parse_extents(self.RAW)
        self.assertEqual(r["run_count"],28)
        self.assertEqual(r["allocated_run_count"],14)
        self.assertEqual(r["unallocated_run_count"],14)
        self.assertEqual(r["allocated_clusters"],143)
        self.assertEqual(r["unallocated_clusters"],81)
        self.assertEqual(r["logical_clusters"],224)
        self.assertTrue(r["allocated_lcn_contiguous"])
        self.assertEqual(r["lcn_discontinuities_between_allocated_runs"],0)
        self.assertEqual(r["first_allocated_lcn"],0x1d52cd)
        self.assertEqual(r["end_allocated_lcn_exclusive"],0x1d535c)

    def test_does_not_depend_on_russian_oem_label(self):
        raw=b"VCN: 0x0  \x84\xab\xa8\xad\xa0: 0x2  LCN: 0x1f\n"
        r=parse_extents(raw)
        self.assertEqual(r["allocated_clusters"],2)

    def test_rejects_gap(self):
        raw=b"VCN: 0x0 LENGTH: 0x2 LCN: 0x30\nVCN: 0x3 LENGTH: 0x2 LCN: 0x40\n"
        with self.assertRaises(ValueError):
            parse_extents(raw)

    def test_discontinuity_detected(self):
        raw=b"VCN: 0x0 LENGTH: 0x2 LCN: 0x30\nVCN: 0x2 LENGTH: 0x2 LCN: 0xffffffffffffffff\nVCN: 0x4 LENGTH: 0x2 LCN: 0x40\n"
        r=parse_extents(raw)
        self.assertEqual(r["lcn_discontinuities_between_allocated_runs"],1)

if __name__=="__main__":
    unittest.main()
