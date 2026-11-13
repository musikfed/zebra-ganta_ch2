#!/usr/bin/env python3
"""Report experiment 009 from ORIGINAL existing CSV on F:. No physical HDD I/O."""
from __future__ import annotations
import argparse,csv,json,statistics,sys
from pathlib import Path

ZONES=(5.0,27.5,50.0,72.5,95.0)
SIZES=(4,64,1024)
def summarize(directory:Path):
    manifest=json.loads((directory/"manifest.json").read_text(encoding="utf-8-sig"))
    if manifest.get("schema")!="zebra-ganta.exp009.v1" or manifest.get("status")!="complete":
        raise ValueError("Not a complete real exp009 manifest")
    with (directory/"observations.csv").open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    with (directory/"summary.csv").open(encoding="utf-8-sig",newline="") as f:
        original_summary=list(csv.DictReader(f))
    n=int(manifest["per_zone"])
    if len(rows)!=5*n*3 or len(original_summary)!=15:
        raise ValueError("Wrong observation or summary count")
    offsets=[]
    records={}
    for r in rows:
        zone=float(r["zone_percent"]);size=int(r["size_kib"])
        if zone not in ZONES or size not in SIZES or int(r["read_bytes"])!=size*1024:
            raise ValueError("Unexpected zone/size/bytes")
        off=int(r["offset_bytes"]);ms=float(r["read_ms"]);mbs=float(r["MB_s"])
        if ms<=0 or mbs<=0 or off%4096: raise ValueError("Invalid latency or offset")
        offsets.append((off,off+size*1024))
        records.setdefault((zone,size),[]).append((ms,mbs))
    for x,y in zip(sorted(offsets),sorted(offsets)[1:]):
        if x[1]>y[0]:raise ValueError("Overlapping read ranges")
    summary=[]
    for zone in ZONES:
        for size in SIZES:
            vals=records.get((zone,size),[])
            if len(vals)!=n:raise ValueError("Unbalanced observations")
            m_ms=statistics.median(x[0] for x in vals)
            m_mbs=statistics.median(x[1] for x in vals)
            reported=[r for r in original_summary if float(r["zone_percent"])==zone and int(r["size_kib"])==size]
            if len(reported)!=1 or abs(m_ms-float(reported[0]["median_read_ms"]))>0.00002 or abs(m_mbs-float(reported[0]["median_MB_s"]))>0.00006:
                raise ValueError("Original summary inconsistent with observations")
            summary.append({"zone_percent":zone,"size_kib":size,"samples":n,
                "median_read_ms":round(m_ms,5),"median_MB_s":round(m_mbs,4),
                "min_read_ms":min(x[0] for x in vals),"max_read_ms":max(x[0] for x in vals)})
    return {"source":str(directory),"source_kind":"REAL HDD WINDOWS USB CSV — not simulated",
        "reads":len(rows),"read_bytes":sum(int(r["read_bytes"]) for r in rows),
        "summary":summary,"caveat":"Block sizes read disjoint LBA areas, not identical locations. Values include disk+USB+Windows effects. No causal proof of macrostripe benefit."}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory",type=Path)
    a=p.parse_args()
    try: print(json.dumps(summarize(a.directory),indent=2,ensure_ascii=False));return 0
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as e:
        print("ERROR:",e,file=sys.stderr);return 1
if __name__=="__main__":raise SystemExit(main())
