import hashlib
import unittest
from tools.publish_acer_raw import csv_info, public_manifest

class PublishAcerRawTests(unittest.TestCase):
    def test_csv_accepts_utf8_bom_and_rows(self):
        rows,fields=csv_info(b"\xef\xbb\xbfpair,mode,target_read_ms\n1,near,12.34\n")
        self.assertEqual(len(rows),1)
        self.assertEqual(fields,{"pair","mode","target_read_ms"})
    def test_csv_rejects_empty_or_broken(self):
        for blob in (b"",b"\xef\xbb\xbf",b"a,b\n1,2,3\n"):
            with self.assertRaises(ValueError):
                csv_info(blob)
    def test_manifest_sensitive_ids_not_exported(self):
        inp={"_digest":"a"*64,"schema":"zebra-ganta.exp008.v1",
             "seed":123,"traces":4,"count_per_trace":128,
             "pnp_ancestors":["PERSONAL_SERIAL"],
             "disk":{"SerialNumber":"PERSONAL_SERIAL","Model":"HGST"},
             "usbview_id":"PERSONAL_SERIAL","format":"NTFS on existing T:"}
        public=public_manifest(inp,"008","source_test",{"observations.csv":{"sha256":"a","rows":512}})
        s=str(public)
        self.assertNotIn("PERSONAL_SERIAL",s)
        self.assertEqual(public["traces"],4)
