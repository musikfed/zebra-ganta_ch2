#!/usr/bin/env python3
r"""Experiment 009: effect of request size on physical HGST read latency.

REAL HGST 2.5-inch Disk 2, existing volume T: NTFS, ORICO SuperSpeed.
Defaults to PLAN ONLY; --run verifies hardware twice and reads raw LBA only.
Nothing is created/modified on T:, no filesystem relocation or formatting.
Not a proof of optimal Zebra macrostripe size.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import random
import statistics
import sys
import time

from experiment004 import verify
from experiment005 import check_usb_parent
from experiment008 import verify_ntfs, validate as validate_identity
from lab import DEFAULT_SIZE

ROOT = Path(__file__).resolve().parent
KIB=1024
SIZES_KIB=(4,64,1024)
ZONES=(5,27.5,50,72.5,95)

def plan(seed=20261113, per_zone=12):
    """Unique 4KiB-aligned nonoverlapping ranges in each of 5 LBA zones.

    Each zone uses 12 slots, each slot has 3 reads at disjoint offsets.
    The 4/64/1024KiB order is rotated, preventing a fixed warmup order.
    """
    if per_zone not in (6,12,24):
        raise ValueError("Only 6, 12 or 24 groups per LBA zone")
    rng=random.Random(seed)
    jobs=[]
    used=[]
    for zone in ZONES:
        # Zone centre. Each group gets a separate ~16MiB chunk;
        # a group has three disjoint 2MiB subslots.
        centre=(int(DEFAULT_SIZE*zone/100)//4096)*4096
        group_indices=list(range(per_zone))
        rng.shuffle(group_indices)
        for n,index in enumerate(group_indices):
            base=centre+(index-per_zone//2)*16*1024*1024
            # Alternate block-size order; no same LBA read twice.
            sizes=list(SIZES_KIB)
            rng.shuffle(sizes)
            for slot,kib in enumerate(sizes):
                off=((base+slot*2*1024*1024)//4096)*4096
                length=kib*KIB
                if off<4096 or off+length>DEFAULT_SIZE:
                    raise ValueError("Unsafe range")
                used.append((off,off+length))
                jobs.append({"zone_percent":zone,"group":index+1,
                    "slot":slot+1,"offset_bytes":off,"read_bytes":length,
                    "size_kib":kib})
    # No range overlaps, even across different request sizes.
    ordered=sorted(used)
    if any(a[1]>b[0] for a,b in zip(ordered,ordered[1:])):
        raise AssertionError("Overlapping LBA ranges")
    return jobs

def save_csv(path,rows):
    if not rows: raise ValueError("No results")
    with path.open("w",encoding="utf-8-sig",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def execute(args,jobs):
    if os.name!="nt" or ROOT.drive.upper()!="F:" or ROOT.name.lower()!="zebra-ganta_ch2":
        raise RuntimeError("Native Windows at F:\\zebra-ganta_ch2 required")
    validate_identity(args)
    initial=verify(args)
    volume=verify_ntfs(args)
    ancestors=check_usb_parent(args)
    print("VERIFIED:",json.dumps({"disk":initial,"volume":volume,
        "USB VID:PID":args.vidpid},ensure_ascii=False))
    print("READ ONLY PhysicalDrive2, existing T: NTFS. No writes to HGST.")
    print("This measures observed Windows + USB read timing, not isolated seek.")
    phrase="READ HGST DISK 2 EXP009"
    if input("Type '"+phrase+"' to confirm: ").strip()!=phrase:
        raise RuntimeError("Cancelled")
    if verify(args)!=initial or verify_ntfs(args)!=volume or check_usb_parent(args)!=ancestors:
        raise RuntimeError("Hardware identity changed after confirmation")
    output=ROOT/"results"/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-exp009-size-ntfs")
    output.mkdir(parents=True,exist_ok=False)
    manifest={"schema":"zebra-ganta.exp009.v1","status":"incomplete",
        "timestamp_utc":datetime.now(timezone.utc).isoformat(),"disk":initial,
        "volume":volume,"bridge":"ORICO USB SuperSpeed VIA Labs 2109:0715",
        "seed":args.seed,"per_zone":args.per_zone,"zones":ZONES,"sizes_kib":SIZES_KIB,
        "read_only":True,"sample_count":len(jobs),
        "limitations":["different LBA for sizes, stratified by zone and separated",
          "Windows/USB/HDD cache is not isolated","USB/OS overhead affects short reads",
          "no direct mechanical seek telemetry","no layout change, no proof of Zebra benefit"]}
    (output/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    records=[]
    try:
        with open(r"\\.\PhysicalDrive2","rb",buffering=0) as handle:
            for i,j in enumerate(jobs,1):
                handle.seek(j["offset_bytes"],os.SEEK_SET)
                begin=time.perf_counter_ns()
                payload=handle.read(j["read_bytes"])
                ms=(time.perf_counter_ns()-begin)/1_000_000
                if len(payload)!=j["read_bytes"]:
                    raise OSError("Short read; abort")
                records.append({**j,"read_ms":round(ms,5),
                    "MB_s":round(j["read_bytes"]/(ms/1000)/1_000_000,4)})
                if i%36==0: print("completed",i,"of",len(jobs),"reads")
    except (OSError,PermissionError) as exc:
        if records:save_csv(output/"observations_partial.csv",records)
        (output/"error.txt").write_text(str(exc),encoding="utf-8")
        raise RuntimeError("Raw reading failed, no retries or bypass: "+str(output)) from exc
    save_csv(output/"observations.csv",records)
    summary=[]
    for zone in ZONES:
        for kib in SIZES_KIB:
            sub=[r for r in records if r["zone_percent"]==zone and r["size_kib"]==kib]
            summary.append({"zone_percent":zone,"size_kib":kib,"samples":len(sub),
                "median_read_ms":round(statistics.median(r["read_ms"] for r in sub),5),
                "median_MB_s":round(statistics.median(r["MB_s"] for r in sub),4)})
    save_csv(output/"summary.csv",summary)
    manifest["status"]="complete"
    (output/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print("SUCCESS:",output)
    print("READ-ONLY HDD observations; not Zebra algorithm acceleration.")
    return 0

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run",action="store_true")
    p.add_argument("--disk",type=int,default=2)
    p.add_argument("--letter",default="T")
    p.add_argument("--size",type=int,default=DEFAULT_SIZE)
    p.add_argument("--win32-size",type=int,default=500105249280)
    p.add_argument("--bridge",default="usb3-orico")
    p.add_argument("--vidpid",default="2109:0715")
    p.add_argument("--link-speed",default="Super")
    p.add_argument("--per-zone",type=int,default=12)
    p.add_argument("--seed",type=int,default=20261113)
    args=p.parse_args()
    try:
        validate_identity(args)
        jobs=plan(args.seed,args.per_zone)
        if not args.run:
            print("PLAN ONLY — no Windows device query, no reads, no files written.")
            print(json.dumps({"device":"HGST Disk 2 / T: NTFS (verified during --run)",
                "sizes_kib":SIZES_KIB,"zones_percent":ZONES,
                "samples":len(jobs),"total_read_bytes":sum(x["read_bytes"] for x in jobs),
                "first_6_jobs":jobs[:6],"write_to_T":False},ensure_ascii=False,indent=2))
            return 0
        return execute(args,jobs)
    except (ValueError,RuntimeError,OSError,ZeroDivisionError) as exc:
        print("ERROR:",exc,file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
