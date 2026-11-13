import unittest
from tools.inspect_extents007d import validate_path

class DVolumeExtentInspectorTests(unittest.TestCase):
    def test_canonical_existing_file_syntax(self):
        self.assertEqual(str(validate_path(r"D:\tools\sample.bin")),r"D:\tools\sample.bin")

    def test_rejects_wrong_drive_traversal_and_special_paths(self):
        bad=[r"T:\a.bin",r"C:\Windows\boot.ini",r"F:\src\a",r"D:\x\..\a",
             r"D:\x\\a",r"D:\x\.\a",r"D:\x\file:ads",
             r"D:/x/y",r"\\.\PhysicalDrive0",r"D:\x\weird. ",
             "D:\\x\nabc",r"D:\a*.bin"]
        for p in bad:
            with self.subTest(p=p), self.assertRaises(ValueError):
                validate_path(p)

if __name__=="__main__":
    unittest.main()
