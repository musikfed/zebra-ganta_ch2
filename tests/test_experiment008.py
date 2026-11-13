import unittest
from lab import DEFAULT_SIZE
from transitions import BLOCK
from experiment008 import plan, validate
from types import SimpleNamespace


class Experiment008PlanTests(unittest.TestCase):
    def test_unique_aligned_within_bounds(self):
        traces=plan(20261113,128,4)
        self.assertEqual([t["mode"] for t in traces],["ordered","shuffled","shuffled","ordered"])
        all_addresses=[o for t in traces for o in t["offsets"]]
        self.assertEqual(len(all_addresses),512)
        self.assertEqual(len(set(all_addresses)),512)
        self.assertTrue(all(BLOCK<=x<DEFAULT_SIZE-BLOCK and x%BLOCK==0 for x in all_addresses))
        self.assertTrue(all(t["offsets"]==sorted(t["offsets"]) for t in traces if t["mode"]=="ordered"))
    def test_deterministic_seed(self):
        self.assertEqual(plan(44,64,4),plan(44,64,4))
        self.assertNotEqual(plan(44,64,4),plan(45,64,4))
    def test_reject_large_unbounded_requests(self):
        for n,traces in [(0,4),(5000,4),(64,2),(64,10)]:
            with self.assertRaises(ValueError):
                plan(1,n,traces)
    def test_reject_wrong_volume_identity(self):
        ok=dict(disk=2,letter="T",size=DEFAULT_SIZE,
                win32_size=500105249280,bridge="usb3-orico",
                vidpid="2109:0715",link_speed="Super")
        validate(SimpleNamespace(**ok))
        for k,v in [("letter","D"),("disk",0),("bridge","usb2-jmicron"),("vidpid","152D:2338"),("link_speed","High")]:
            wrong=dict(ok);wrong[k]=v
            with self.assertRaises(RuntimeError):
                validate(SimpleNamespace(**wrong))

if __name__=="__main__":
    unittest.main()
