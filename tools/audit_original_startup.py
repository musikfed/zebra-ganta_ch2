#!/usr/bin/env python3
"""Read-only audit of original archived HGST experiments 003, 008, 009.

No device I/O. Prints raw first-operation startup latency and adjusted
trace accounting. Excluding the first operation is a SENSITIVITY CHECK,
not deletion of measured data nor proof of specific mechanical mechanism.
"""
from __future__ import annotations
import argparse,csv,json,statistics,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"data"/"raw"

def load(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def report(root=BASE):
    cold=[]
    for n in range(1,4):
        path=root/f"exp003-run{n}"/"observations.csv"
        rows=load(path)
        if not rows or rows[0]["pair"]!="1" or rows[0]["mode"]!="near":
            raise ValueError(f"unexpected first observation in exp003 run {n}")
        cold.append({"experiment":f"003-run{n}","first_operation_kind":"anchor raw 4KiB read",
            "first_operation_ms":float(rows[0]["anchor_ms"])})
    obs=load(root/"exp008-ntfs-hgst"/"observations.csv")
    summary=load(root/"exp008-ntfs-hgst"/"summary.csv")
    if len(obs)!=512 or len(summary)!=4:raise ValueError("Incorrect exp008 row count")
    grouped={}
    for row in obs: grouped.setdefault(int(row["trace"]),[]).append(row)
    results=[]
    for s in summary:
        i=int(s["trace"])
        entries=sorted(grouped[i],key=lambda row:int(row["sequence"]))
        if len(entries)!=128 or int(entries[0]["sequence"])!=1:raise ValueError("Incorrect exp008 sequence")
        first=float(entries[0]["target_read_ms"])
        wall=float(s["total_wall_ms"])
        if wall<=first:raise ValueError("Wall less than first read")
        results.append({"trace":i,"mode":s["mode"],"full_wall_ms":wall,
             "first_read_ms":first,"wall_minus_first_read_ms":round(wall-first,4),
             "remaining_reads":127})
    cold.append({"experiment":"008-trace1","first_operation_kind":"first raw 4KiB read",
        "first_operation_ms":results[0]["first_read_ms"]})
    if results[0]["trace"]!=1:raise ValueError("Trace accounting unexpected")
    n9=load(root/"exp009-size-ntfs"/"observations.csv")
    if len(n9)!=180 or n9[0]["size_kib"]!="1024":raise ValueError("Unexpected exp009 startup")
    cold.append({"experiment":"009","first_operation_kind":"first raw 1MiB read",
        "first_operation_ms":float(n9[0]["read_ms"])})
    by_mode={}
    for mode in ("ordered","shuffled"):
        subset=[x for x in results if x["mode"]==mode]
        if len(subset)!=2:raise ValueError("Unbalanced modes")
        by_mode[mode]={
            "median_full_wall_ms":round(statistics.median(x["full_wall_ms"] for x in subset),4),
            "median_wall_minus_first_ms":round(statistics.median(x["wall_minus_first_read_ms"] for x in subset),4)}
    return {"source":"data/raw original GitHub CSV","device":"HGST Disk 2, NTFS T:",
        "startup_samples":cold,
        "startup_min_ms":min(x["first_operation_ms"] for x in cold),
        "startup_max_ms":max(x["first_operation_ms"] for x in cold),
        "exp008_traces":results,"exp008_by_mode":by_mode,
        "caution":"The first-read adjustment is an illustrative sensitivity analysis, NOT a replacement for original full wall time. Other first-read effects may differ; root cause unverified. Distinct LBA sets in ordered and shuffled traces. No claimed Zebra placement acceleration."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-root",type=Path,default=BASE)
    a=p.parse_args()
    try:print(json.dumps(report(a.raw_root),ensure_ascii=False,indent=2));return 0
    except (KeyError,ValueError,OSError) as exc:print("ERROR:",exc,file=sys.stderr);return 1
if __name__=="__main__":raise SystemExit(main())
