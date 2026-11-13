#!/usr/bin/env python3
"""Read-only offline analysis of exp005 observations; never opens a physical drive."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys

# Allow root-level experiment005 import when running tools/report_exp005.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def median(values):
    return round(statistics.median(values),5) if values else None

def analyze(path: Path):
    folder=path if path.is_dir() else path.parent
    manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema")!="zebra-ganta.exp005.v1" or manifest.get("status")!="complete":
        raise ValueError("Expected completed experiment005 manifest")
    with (folder/"observations.csv").open(encoding="utf-8-sig",newline="") as fp:
        rows=list(csv.DictReader(fp))
    if len(rows)!=manifest["pairs"]*8:
        raise ValueError("Unexpected number of observations")
    data={}
    seen=set()
    for row in rows:
        pair=int(row["pair"]);rnd=int(row["round"]);slot=int(row["slot"]);mode=row["mode"]
        if not(1<=pair<=manifest["pairs"] and 1<=rnd<=4 and 1<=slot<=2
                and mode in ("near","far")):
            raise ValueError("Invalid observation coordinates")
        key=(pair,rnd,slot)
        if key in seen:raise ValueError("Duplicate observation")
        seen.add(key)
        data[key]={"mode":mode,"latency":float(row["target_read_ms"]),
                   "anchor_latency":float(row["anchor_ms"])}
    from experiment005 import ROUNDS
    for pair in range(1,manifest["pairs"]+1):
        for rnd in range(1,5):
            for slot,mode in enumerate(ROUNDS[rnd-1],1):
                if data[pair,rnd,slot]["mode"]!=mode:
                    raise ValueError("ABBA order mismatch")
    summary={}
    for mode in ("near","far"):
        summary[mode]={"n":sum(r["mode"]==mode for r in data.values()),
            "median_ms":median([r["latency"] for r in data.values() if r["mode"]==mode]),
            "slot1_median_ms":median([r["latency"] for (p,round_,slot),r in data.items()
                                    if r["mode"]==mode and slot==1]),
            "slot2_median_ms":median([r["latency"] for (p,round_,slot),r in data.items()
                                    if r["mode"]==mode and slot==2]),
            "anchor_median_ms":median([r["anchor_latency"] for r in data.values() if r["mode"]==mode])}
    pairs=[]
    for pair in range(1,manifest["pairs"]+1):
        diffs=[]
        for rnd in range(1,5):
            near=next(data[pair,rnd,s]["latency"] for s in (1,2) if data[pair,rnd,s]["mode"]=="near")
            far=next(data[pair,rnd,s]["latency"] for s in (1,2) if data[pair,rnd,s]["mode"]=="far")
            diffs.append(far-near)
        pairs.append(median(diffs))
    # Distinguish first exposure from repeated reads at the SAME LBA locations.
    # Do not assume sub-millisecond values are physical head movements.
    by_round = {}
    for rnd in range(1,5):
        samples = [r for (p,rr,s),r in data.items() if rr == rnd]
        by_round[str(rnd)] = {
            "count":len(samples),
            "near_median_ms":median([r["latency"] for r in samples if r["mode"]=="near"]),
            "far_median_ms":median([r["latency"] for r in samples if r["mode"]=="far"]),
            "anchor_median_ms":median([r["anchor_latency"] for r in samples]),
            "target_below_1ms_count":sum(r["latency"] < 1 for r in samples)
        }
    first = [r for (p,rr,s),r in data.items() if rr == 1]
    later = [r for (p,rr,s),r in data.items() if rr > 1]
    summary["rounds"] = by_round
    summary["first_round_target_median_ms"] = median([r["latency"] for r in first])
    summary["later_rounds_target_median_ms"] = median([r["latency"] for r in later])
    summary["all_targets_below_1ms_count"] = sum(r["latency"] < 1 for r in data.values())
    summary["all_anchors_below_1ms_count"] = sum(r["anchor_latency"] < 1 for r in data.values())
    summary["paired_delta_median_ms"]=median(pairs)
    summary["positive_pair_count"]=sum(x>0 for x in pairs)
    summary["negative_pair_count"]=sum(x<0 for x in pairs)
    return {"experiment":"005","source":str(folder),"pairs":manifest["pairs"],
            "target_reads":len(rows),"read_only_analysis":True,
            "metrics":summary,
            "warning":"Same LBA blocks repeat 4 rounds; sub-millisecond times suggest cache or short-circuiting, not physical seek. ABBA alone does not isolate disk mechanics."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder",type=Path)
    args=p.parse_args()
    try:
        print(json.dumps(analyze(args.folder),ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print("ERROR:",exc,file=sys.stderr)
        return 1
if __name__=="__main__":
    raise SystemExit(main())
