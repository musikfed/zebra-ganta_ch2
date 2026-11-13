import csv
import json
import tempfile
import unittest
from pathlib import Path
from tools.report_exp009 import summarize, ZONES, SIZES

class Report009Tests(unittest.TestCase):
    def fixture(self, path):
        p=Path(path)
        (p/"manifest.json").write_text(json.dumps({"schema":"zebra-ganta.exp009.v1","status":"complete","per_zone":1}),encoding="utf8")
        observations=[]
        summary=[]
        j=0
        for zone in ZONES:
            for size in SIZES:
                offset=4096+j*2_097_152;j+=1
                observations.append({"zone_percent":zone,"size_kib":size,"read_bytes":size*1024,"offset_bytes":offset,"read_ms":2.0,"MB_s":3.0})
                summary.append({"zone_percent":zone,"size_kib":size,"samples":1,"median_read_ms":2.0,"median_MB_s":3.0})
        for name,rows in [("observations.csv",observations),("summary.csv",summary)]:
            with (p/name).open("w",encoding="utf-8-sig",newline="") as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        return p
    def test_valid_originals(self):
        with tempfile.TemporaryDirectory() as d:
            out=summarize(self.fixture(d))
            self.assertEqual(out["reads"],15)
            self.assertEqual(len(out["summary"]),15)
    def test_detect_corrupted_summary(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.fixture(d)
            s=(p/"summary.csv").read_text(encoding="utf-8-sig").replace("2.0,3.0","9.0,3.0",1)
            (p/"summary.csv").write_text(s,encoding="utf-8-sig")
            with self.assertRaisesRegex(ValueError,"inconsistent"):
                summarize(p)
