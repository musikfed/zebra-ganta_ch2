import unittest

from lab import ALIGNMENT, DEFAULT_SIZE, identify, offsets


class LabTests(unittest.TestCase):
    def setUp(self):
        self.disk = {
            "Number": 2, "Model": "HGST HTS 725050B7E630 USB Device",
            "FriendlyName": "HGST HTS 725050B7E630", "Size": DEFAULT_SIZE,
            "Win32Size": 500_105_249_280,
            "BusType": "USB", "IsBoot": False, "IsSystem": False,
            "IsOffline": False, "OperationalStatus": "Online",
        }

    def test_identifies_exact_target(self):
        self.assertEqual(identify([self.disk], 2, "HTS725050B7E630", DEFAULT_SIZE), self.disk)

    def test_rejects_wrong_model(self):
        with self.assertRaisesRegex(RuntimeError, "model mismatch"):
            identify([self.disk], 2, "OTHER", DEFAULT_SIZE)

    def test_rejects_wrong_capacity(self):
        with self.assertRaisesRegex(RuntimeError, "size mismatch"):
            identify([self.disk], 2, "HTS725050B7E630", DEFAULT_SIZE - 1)

    def test_rejects_bad_win32_capacity(self):
        self.disk["Win32Size"] = 0
        with self.assertRaisesRegex(RuntimeError, "Win32 disk capacity"):
            identify([self.disk], 2, "HTS725050B7E630", DEFAULT_SIZE)

    def test_rejects_system_disk(self):
        self.disk["IsSystem"] = True
        with self.assertRaisesRegex(RuntimeError, "system or boot"):
            identify([self.disk], 2, "HTS725050B7E630", DEFAULT_SIZE)

    def test_rejects_offline_disk(self):
        self.disk["IsOffline"] = True
        with self.assertRaisesRegex(RuntimeError, "offline"):
            identify([self.disk], 2, "HTS725050B7E630", DEFAULT_SIZE)

    def test_rejects_non_usb_disk(self):
        self.disk["BusType"] = "SATA"
        with self.assertRaisesRegex(RuntimeError, "USB"):
            identify([self.disk], 2, "HTS725050B7E630", DEFAULT_SIZE)

    def test_samples_aligned_in_range(self):
        sample = offsets(DEFAULT_SIZE, 5, 16 * 1024 * 1024)
        self.assertEqual(len(sample), 5)
        self.assertEqual(len({off for _, off in sample}), 5)
        for _, off in sample:
            self.assertEqual(off % ALIGNMENT, 0)
            self.assertGreater(off, 0)
            self.assertLess(off + 16 * 1024 * 1024, DEFAULT_SIZE)

    def test_rejects_oversized_samples(self):
        with self.assertRaises(ValueError):
            offsets(DEFAULT_SIZE, 22, 16 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
