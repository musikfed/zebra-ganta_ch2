import unittest
from unittest.mock import patch
from io import StringIO
from tools.inspect_extents007 import main
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


    def test_t_volume_plan_does_not_query_hardware(self):
        with patch("sys.argv",["inspect_extents007.py","--volume"]), \
             patch("tools.inspect_extents007.run_volume",side_effect=AssertionError("live query not allowed")), \
             patch("sys.stdout",new_callable=StringIO) as out:
            self.assertEqual(main(),0)
            self.assertIn("PLAN ONLY",out.getvalue())

    def test_t_volume_requires_explicit_run(self):
        with patch("sys.argv",["inspect_extents007.py","--volume","--run"]), \
             patch("tools.inspect_extents007.run_volume",return_value=0) as live:
            self.assertEqual(main(),0)
            live.assert_called_once_with()

    def test_file_and_volume_mutually_exclusive(self):
        with patch("sys.argv",["inspect_extents007.py","--volume","--file",r"T:\foo.bin"]), \
             patch("sys.stderr",new_callable=StringIO) as errors:
            self.assertEqual(main(),1)
            self.assertIn("exactly one",errors.getvalue())

if __name__=="__main__":
    unittest.main()
