import io
import unittest

from lab import DEFAULT_SIZE
from transitions import BLOCK, MAX_PAIRS, MIN_GAP, plan, single_read


class Chapter3Tests(unittest.TestCase):
    def test_plan_has_correct_count_and_spacing(self):
        jobs = plan(DEFAULT_SIZE, 40, 20261112)
        self.assertEqual(len(jobs), 40)
        self.assertEqual(len({item[0] for item in jobs}), 40)
        for home, near, far in jobs:
            self.assertEqual(near-home, MIN_GAP)
            self.assertGreater(far-home, DEFAULT_SIZE//4)
            self.assertTrue(all(0 < x < DEFAULT_SIZE-BLOCK for x in (home, near, far)))
            self.assertTrue(all(x % BLOCK == 0 for x in (home, near, far)))

    def test_seed_is_reproducible(self):
        self.assertEqual(plan(DEFAULT_SIZE, 40, 123), plan(DEFAULT_SIZE, 40, 123))
        self.assertNotEqual(plan(DEFAULT_SIZE, 40, 123), plan(DEFAULT_SIZE, 40, 456))

    def test_bounds_prevent_unintended_long_test(self):
        for count in (0, 3, MAX_PAIRS + 1):
            with self.assertRaises(ValueError):
                plan(DEFAULT_SIZE, count, 1)

    def test_mock_read_is_only_4k_and_at_requested_offset(self):
        obj = io.BytesIO(b"x"*(4*BLOCK))
        value = single_read(obj, 2*BLOCK)
        self.assertGreaterEqual(value, 0)
        self.assertEqual(obj.tell(), 3*BLOCK)

    def test_mock_short_read_rejected(self):
        obj = io.BytesIO(b"x"*(BLOCK//2))
        with self.assertRaises(OSError):
            single_read(obj, 0)


if __name__ == "__main__":
    unittest.main()
