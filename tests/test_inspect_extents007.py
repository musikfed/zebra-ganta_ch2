import unittest
from tools.inspect_extents007 import validate_selected

class Extents007Tests(unittest.TestCase):
    def test_accepts_explicit_ntfs_file_path_only(self):
        self.assertEqual(str(validate_selected(r"T:\TestData\sample.bin")),r"T:\TestData\sample.bin")

    def test_rejects_untrusted_paths(self):
        for path in (r"C:\Windows\boot.ini",r"F:\zebra-ganta_ch2\README.md",
                     r"\\.\PhysicalDrive2",r"T:\a\..\b",r"T:\a\\b",
                     r"T:\a\.\b","T:\\a\nb",'T:\\x"y'):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    validate_selected(path)

if __name__=="__main__":
    unittest.main()
