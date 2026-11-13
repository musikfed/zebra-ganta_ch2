#!/usr/bin/env python3
"""Read-only analysis of original experiment 008 files on F:.

No HDD access, no invented results. Distinguishes LBA access ordering
from NTFS file placement and physical head positioning.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys

MODES=("ordered","shuffled")

def percentile(data, pct):
    if not data: raise ValueError("No values")
    values=sorted(data)
    i=(len(values)-1)*pct/100.0
    lo=int(i)
    hi=min(lo+1,len(values)-1)
    return values[lo]*(1-(i-lo))+values[hi]*(i-lo)

def analyze(directory: Path):
    manifest_path=directory/"manifest.json"
    rows_path=directory/"observations.csv"
    summary_path=directory/"summary.csv"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema")!="zebra-ganta.exp008.v1" or manifest.get("status")!="complete":
        raise ValueError("Refusing incomplete or unrelated experiment 008")
    with rows_path.open(encoding="utf-8-sig",newline="") as f:
        observations=list(csv.DictReader(f))
    with summary_path.open(encoding="utf-8-sig",newline="") as f:
        summaries=list(csv.DictReader(f))
    count=int(manifest["count_per_trace"])
    num=int(manifest["traces"])
    if len(observations)!=count*num or len(summaries)!=num:
        raise ValueError("Missing/extra original observations or trace summaries")
    all_offsets=set()
    by_trace={}
    for row in observations:
        t=int(row["trace"])
        mode=row["mode"]
        index=int(row["sequence"])
        offset=int(row["offset_bytes"])
        read_bytes=int(row["read_bytes"])
        latency=float(row["target_read_ms"])
        if t not in range(1,num+1) or mode not in MODES or read_bytes!=4096 or not (latency>=0):
            raise ValueError("Invalid observation record")
        if offset in all_offsets:
            raise ValueError("Duplicate address found: result invalid for exp008")
        all_offsets.add(offset)
        by_trace.setdefault(t,[]).append((index,mode,latency,offset))
    stats=[]
    for row in summaries:
        t=int(row["trace"])
        mode=row["mode"]
        obs=by_trace.get(t,[])
        if len(obs)!=count or any(r[1]!=mode for r in obs) or sorted(r[0] for r in obs)!=list(range(1,count+1)):
            raise ValueError("Trace identity/order mismatch")
        if mode not in MODES or int(row["reads"])!=count:
            raise ValueError("Trace size mismatch")
        wall=float(row["total_wall_ms"])
        if wall<=0: raise ValueError("Invalid wall time")
        latencies=[r[2] for r in obs]
        offsets=[r[3] for r in sorted(obs)]
        if mode=="ordered" and offsets!=sorted(offsets):
            raise ValueError("Ordered trace not ordered")
        jump_sum=sum(abs(b-a) for a,b in zip(offsets,offsets[1:]))
        if jump_sum!=int(row["jump_sum_bytes"]):
            raise ValueError("Trace jump sum differs from original observations")
        stats.append({"trace":t,"mode":mode,"reads":count,
                      "total_wall_ms":wall,
                      "p50_ms":round(percentile(latencies,50),4),
                      "p95_ms":round(percentile(latencies,95),4),
                      "p99_ms":round(percentile(latencies,99),4),
                      "sub_1ms":sum(v<1 for v in latencies),
                      "jump_sum_bytes":jump_sum})
    if sorted(s["mode"] for s in stats)!=sorted(["ordered","shuffled"]*(num//2)):
        raise ValueError("Unbalanced experimental mode allocation")
    comparison={}
    for mode in MODES:
        sub=[r for r in stats if r["mode"]==mode]
        comparison[mode]={"trace_count":len(sub),
            "median_total_wall_ms":round(statistics.median(r["total_wall_ms"] for r in sub),4),
            "median_p95_ms":round(statistics.median(r["p95_ms"] for r in sub),4),
            "median_jump_sum_bytes":statistics.median(r["jump_sum_bytes"] for r in sub)}
    return {"source_folder":str(directory),"experiment":8,
            "source_kind":"ORIGINAL REAL HDD CSV, NOT SIMULATED",
            "trace_stats":sorted(stats,key=lambda d:d["trace"]),
            "by_mode":comparison,
            "caveat":"Different unique, approximately radial-matched LBA in modes. Windows/USB/HDD cache not isolated. No proof of Zebra file placement speedup."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("result_directory",type=Path)
    args=p.parse_args()
    try: r=analyze(args.result_directory)
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print("ERROR:",exc,file=sys.stderr);return 1
    print(json.dumps(r,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
