#!/usr/bin/env python3
"""Secondary analysis of EXISTING exp008 CSV; zero device reads.

Explores confounding by start-up, logical jump distance and LBA zone.
Descriptive only: no causal claim about head mechanics or Zebra placement.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
from statistics import median
import sys

from tools.report_exp008 import analyze

DISK_SIZE=500106780160

def spearman(xs,ys):
    """Rank correlation with average ranks for ties. Return None if constant."""
    if len(xs)!=len(ys) or len(xs)<3: return None
    def ranks(vals):
        index=sorted(range(len(vals)),key=lambda i: vals[i])
        result=[0.0]*len(vals)
        k=0
        while k<len(index):
            z=k+1
            while z<len(index) and vals[index[z]]==vals[index[k]]:z+=1
            mean=(k+1+z)/2
            for j in index[k:z]:result[j]=mean
            k=z
        return result
    a,b=ranks(xs),ranks(ys)
    av=sum(a)/len(a);bv=sum(b)/len(b)
    num=sum((x-av)*(y-bv) for x,y in zip(a,b))
    ax=sum((x-av)**2 for x in a);by=sum((y-bv)**2 for y in b)
    return round(num/math.sqrt(ax*by),5) if ax>0 and by>0 else None

def inspect(directory:Path):
    verified=analyze(directory)
    with (directory/"observations.csv").open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    by={}
    for r in rows:
        t=int(r["trace"]);by.setdefault(t,[]).append(r)
    traces=[]
    for trace, entries in sorted(by.items()):
        entries.sort(key=lambda r:int(r["sequence"]))
        lat=[float(r["target_read_ms"]) for r in entries]
        jumps=[int(r["jump_bytes"]) for r in entries]
        offsets=[int(r["offset_bytes"]) for r in entries]
        # The first read has no jump within a trace and must be excluded
        # from any within-trace correlation.
        noninitial=[(j,l) for j,l in zip(jumps[1:],lat[1:])]
        bands=[]
        for z in range(5):
            subset=[v for o,v in zip(offsets,lat) if int(o/DISK_SIZE*5)==z]
            bands.append({"band_percent":f"{z*20}-{(z+1)*20}","reads":len(subset),
                          "median_read_ms":round(median(subset),5) if subset else None})
        traces.append({"trace":trace,"mode":entries[0]["mode"],
            "initial_read_ms":lat[0],
            "median_subsequent_ms":round(median(lat[1:]),5),
            "max_read_ms":max(lat),
            "jump_latency_spearman":spearman([v[0] for v in noninitial],[v[1] for v in noninitial]),
            "lba_zone_medians":bands})
    return {"experiment":8,"source_kind":"original_local_CSV_read_only",
       "traces":traces,"summary_verified":len(verified["trace_stats"]),
       "interpretation":"Descriptive secondary analysis; separate LBA sets by mode; no real NTFS relocation, seek telemetry or algorithm gain."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory",type=Path)
    a=p.parse_args()
    try:
        print(json.dumps(inspect(a.directory),ensure_ascii=False,indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("ERROR:",exc,file=sys.stderr);return 1

if __name__=="__main__":
    raise SystemExit(main())
