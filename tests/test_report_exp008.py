import csv
import json
import tempfile
import unittest
from pathlib import Path
from tools.report_exp008 import analyze, percentile


class Exp008ReportTests(unittest.TestCase):
    def make_fixture(self, base):
        base=Path(base)
        (base/"manifest.json").write_text(json.dumps({"schema":"zebra-ganta.exp008.v1","status":"complete","count_per_trace":2,"traces":4}),encoding="utf-8")
        values=[
          (1,"ordered",[4096,8192],[8,9]),
          (2,"shuffled",[16384,12288],[11,12]),
          (3,"shuffled",[24576,20480],[10,12]),
          (4,"ordered",[28672,32768],[7,8])]
        obs=[]
        stats=[]
        for t,mode,offsets,ms in values:
            for i,(off,lat) in enumerate(zip(offsets,ms),1):
                obs.append({"trace":t,"mode":mode,"sequence":i,"offset_bytes":off,"jump_bytes":0 if i==1 else 4096,"read_bytes":4096,"target_read_ms":lat})
            stats.append({"trace":t,"mode":mode,"reads":2,"total_wall_ms":sum(ms)+1,"median_read_ms":sum(ms)/2,"jump_sum_bytes":4096})
        for filename,rows in [("observations.csv",obs),("summary.csv",stats)]:
            with (base/filename).open("w",newline="",encoding="utf-8-sig") as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        return base

    def test_success(self):
        with tempfile.TemporaryDirectory() as temp:
            result=analyze(self.make_fixture(temp))
            self.assertEqual(len(result["trace_stats"]),4)
            self.assertEqual(result["by_mode"]["ordered"]["trace_count"],2)

    def test_duplicate_offset_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.make_fixture(temp)
            fp=p/"observations.csv"
            content=fp.read_text(encoding="utf-8-sig").replace("32768","4096")
            fp.write_text(content,encoding="utf-8-sig")
            with self.assertRaisesRegex(ValueError,"Duplicate address"):
                analyze(p)

    def test_percentile(self):
        self.assertEqual(percentile([1,2,3],50),2)
        self.assertEqual(percentile([1,2,3],95),2.9)


if __name__=="__main__":
    unittest.main()
