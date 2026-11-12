#!/usr/bin/env python3
"""Compare actual HGST USB2/USB3 lab and near/far observations, never invent data.
Reads existing CSV files only; writes no files and never opens a physical drive.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
import statistics
import sys
import json

# Allow imports from the repository root when invoked as tools/compare_usb_bridges.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def scan(path: Path) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as fp:
        rows=list(csv.DictReader(fp))
    if not rows or not {"position_percent","MB_s","read_bytes"}.issubset(rows[0]):
        raise ValueError(f"Not a lab measurements.csv: {path}")
    values=[float(row["MB_s"]) for row in rows]
    if any(x<=0 for x in values):
        raise ValueError(f"Nonpositive rate: {path}")
    points={}
    for row in rows:
        point=float(row["position_percent"])
        points.setdefault(point,[]).append(float(row["MB_s"]))
    return {"file":str(path),"n":len(values),
            "median_MB_s":round(statistics.median(values),4),
            "position_medians_MB_s":{str(k):round(statistics.median(v),4)
                                      for k,v in sorted(points.items())}}

def transitions(path: Path) -> dict:
    from analyze_transitions import summarize
    return summarize(path)

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--usb2-scan",type=Path,required=True)
    p.add_argument("--usb3-scan",type=Path,required=True)
    p.add_argument("--usb2-transitions",type=Path)
    p.add_argument("--usb3-transitions",type=Path)
    a=p.parse_args()
    if bool(a.usb2_transitions)!=bool(a.usb3_transitions):
        p.error("Provide BOTH transition CSVs or neither")
    try:
        first=scan(a.usb2_scan);second=scan(a.usb3_scan)
        if set(first["position_medians_MB_s"])!=set(second["position_medians_MB_s"]):
            raise ValueError("Different LBA zone labels: scans are not directly comparable")
        output={"experiment":"004","status":"observed CSV comparison (Windows + USB, not head seek)",
                "usb2":first,"usb3":second,
                "usb3_over_usb2_ratio_of_medians":
                    round(second["median_MB_s"]/first["median_MB_s"],4),
                "warning":"A difference can be caused by bridge, negotiated USB speed, caching, temperature or order. It does NOT establish optimization speedup."}
        if a.usb2_transitions:
            output["transitions"]={"usb2":transitions(a.usb2_transitions),
                                   "usb3":transitions(a.usb3_transitions)}
        print(json.dumps(output,ensure_ascii=False,indent=2))
        return 0
    except (OSError, ValueError, KeyError, ZeroDivisionError) as e:
        print("ERROR:",e,file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
