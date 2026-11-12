#!/usr/bin/env python3
"""Read-only report from existing experiment 004 outputs; no disk device reads."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys

def read_csv(path):
    with path.open(encoding="utf-8-sig",newline="") as fp:
        return list(csv.DictReader(fp))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder",type=Path,help="Existing exp004 result folder")
    a=p.parse_args()
    folder=a.folder.resolve()
    try:
        manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
        rows=read_csv(folder/"measurements.csv")
        pairs=read_csv(folder/"observations.csv")
        if not rows or not pairs:
            raise ValueError("Empty measurement or observation file")
        if not {"position_percent","MB_s"}.issubset(rows[0]):
            raise ValueError("Unexpected measurements.csv columns")
        if not {"pair","mode","target_read_ms"}.issubset(pairs[0]):
            raise ValueError("Unexpected observations.csv columns")
        rates=[float(r["MB_s"]) for r in rows]
        zones={}
        for r in rows:
            zones.setdefault(float(r["position_percent"]),[]).append(float(r["MB_s"]))
        modes={}
        for r in pairs:
            key=int(r["pair"])
            mode=r["mode"]
            if mode not in ("near","far") or mode in modes.setdefault(key,{}):
                raise ValueError("Duplicate/unexpected near-far pair")
            modes[key][mode]=float(r["target_read_ms"])
        if not modes or any(set(v)!={"near","far"} for v in modes.values()):
            raise ValueError("Missing near/far observations")
        near=[v["near"] for v in modes.values()]
        far=[v["far"] for v in modes.values()]
        delta=[v["far"]-v["near"] for v in modes.values()]
        print(json.dumps({
            "experiment":manifest.get("schema"),
            "folder":str(folder),
            "bridge":manifest.get("bridge"),
            "usbview_link_speed_reported":manifest.get("usbview_negotiated_link_speed_manual"),
            "usbview_vidpid_reported":manifest.get("usbview_vidpid_manual"),
            "measurement_count":len(rates),
            "throughput_median_MB_s":round(statistics.median(rates),4),
            "throughput_min_max_MB_s":[min(rates),max(rates)],
            "zone_median_MB_s":{str(x):round(statistics.median(v),4) for x,v in sorted(zones.items())},
            "near_far_pair_count":len(delta),
            "near_median_ms":round(statistics.median(near),4),
            "far_median_ms":round(statistics.median(far),4),
            "difference_of_medians_ms":round(statistics.median(far)-statistics.median(near),4),
            "median_of_paired_differences_ms":round(statistics.median(delta),4),
            "far_slower_count":sum(x>0 for x in delta),
            "far_faster_count":sum(x<0 for x in delta),
            "equal_count":sum(x==0 for x in delta),
            "warning":"Windows+USB observed latency; no isolated mechanical seek-time or algorithm speedup claim"
        },ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print("ERROR:",exc,file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
