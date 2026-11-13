import csv
import io
import json
import unittest
from tools.publish_exp010_acer import OBS_COLUMNS, SUMMARY_COLUMNS, validate


def csv_blob(fields, rows):
    stream=io.StringIO()
    writer=csv.DictWriter(stream,fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


class PublishExperiment010Tests(unittest.TestCase):
    def original(self):
        obs=[]
        for i, p in enumerate((2,0,10,2,10,2,0,0,10),1):
            off=4096+i*100000*4096
            obs.append({"session":i,"pause_after_open_s":p,
                "first_offset":off,"second_offset":off+2097152,
                "read_bytes":4096,"open_ms":float(i),
                "first_read_ms":float(i+2),"second_read_ms":float(i+4)})
        summaries=[]
        for p in (0,2,10):
            sub=[row for row in obs if row["pause_after_open_s"]==p]
            import statistics
            summaries.append({"pause_after_open_s":p,"sessions":3,
                "median_open_ms":statistics.median(x["open_ms"] for x in sub),
                "median_first_ms":statistics.median(x["first_read_ms"] for x in sub),
                "median_second_ms":statistics.median(x["second_read_ms"] for x in sub)})
        manifest={"schema":"zebra-ganta.exp010.v1","status":"complete",
            "seed":20261113,"sessions":9,"reads_per_session":2,
            "block_bytes":4096,"pauses_after_handle_open_s":[0,2,10],
            "disk":{"SerialNumber":"PRIVATE123"}}
        return csv_blob(OBS_COLUMNS,obs),csv_blob(SUMMARY_COLUMNS,summaries),json.dumps(manifest).encode()

    def test_valid_and_private_manifest_not_exported(self):
        a,b,c=self.original()
        result=validate(a,b,c)
        self.assertEqual(result["files"]["observations.csv"]["rows"],9)
        self.assertNotIn("PRIVATE123",json.dumps(result))

    def test_reject_corrupted_summary(self):
        a,b,c=self.original()
        with self.assertRaises(ValueError):
            validate(a,b.replace(b"10.0",b"99.0"),c)

    def test_reject_unexpected_column(self):
        a,b,c=self.original()
        with self.assertRaises(ValueError):
            validate(a.replace(b"open_ms",b"serial_"),b,c)
