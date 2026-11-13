#!/usr/bin/env python3
r"""Experiment 011: refine the observed post-open idle pause/first-read association.

PLAN ONLY by default, without disk or Windows inventory access.
LIVE requires HGST Disk 2, T: NTFS and ORICO VIA 2109:0715, verified twice;
36 unique 4KiB raw reads, 18 short handle sessions, only output on F:.
No sleep/standby/spin-down commands, no NTFS writes or relocation.
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
from experiment008 import validate as validate_hgst, verify_ntfs
from lab import DEFAULT_SIZE
from transitions import BLOCK, single_read

ROOT=Path(__file__).resolve().parent
PAUSES=(0,1,3,5,7,10)
REPETITIONS=3
OFFSET_GAP=2*1024*1024

def plan(seed=20261113):
    if not isinstance(seed,int) or seed<0 or seed>=2**32:
        raise ValueError("seed outside bounded range")
    rng=random.Random(seed)
    delays=list(PAUSES)*REPETITIONS
    rng.shuffle(delays)
    used=set()
    jobs=[]
    for i,delay in enumerate(delays,1):
        # Space chosen pseudo-randomly inside 10%-90% of disk, with no repeats.
        first=(int(DEFAULT_SIZE*(0.10+0.8*rng.random()))//BLOCK)*BLOCK
        second=first+OFFSET_GAP
        if first<=0 or second+BLOCK>DEFAULT_SIZE or first in used or second in used:
            raise ValueError("Duplicate or unsafe LBA offset")
        used.update((first,second))
        jobs.append({"session":i,"pause_after_open_s":delay,
                     "first_offset":first,"second_offset":second,"read_bytes":BLOCK})
    if len(used)!=2*len(jobs) or any(delays.count(x)!=REPETITIONS for x in PAUSES):
        raise AssertionError("Invalid plan")
    return jobs

def csv_write(path,rows):
    if not rows:raise ValueError("No rows")
    with path.open("w",encoding="utf-8-sig",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)

def execute(args,jobs):
    if os.name!="nt" or str(ROOT).lower()!=r"f:\zebra-ganta_ch2":
        raise RuntimeError("Use Windows F:\\zebra-ganta_ch2 only")
    validate_hgst(args)
    disk=verify(args);volume=verify_ntfs(args);parent=check_usb_parent(args)
    print("VERIFIED:",json.dumps({"disk":disk,"volume":volume,"usb_parent":"2109:0715"},ensure_ascii=False))
    print("READ ONLY: 18 sessions, 36 unique 4096-byte reads; NEVER writes T:.")
    confirmation="READ HGST DISK 2 EXP011"
    if input("Type '"+confirmation+"' to run: ").strip()!=confirmation:
        raise RuntimeError("Cancelled")
    if verify(args)!=disk or verify_ntfs(args)!=volume or check_usb_parent(args)!=parent:
        raise RuntimeError("Device identity changed after confirmation")
    output=ROOT/"results"/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-exp011-idle-threshold-ntfs")
    output.mkdir(parents=True,exist_ok=False)
    manifest={"schema":"zebra-ganta.exp011.v1","status":"incomplete",
       "created_utc":datetime.now(timezone.utc).isoformat(),"disk":disk,"volume":volume,
       "seed":args.seed,"pauses_s":PAUSES,"repetitions":REPETITIONS,
       "sessions":len(jobs),"block_bytes":BLOCK,"read_only":True,
       "limitations":["No actual spindle/USB energy state captured",
         "Pauses occur after opening raw device handle, NOT after last physical disk I/O",
         "Different LBA for every first and second read",
         "Potential Windows/USB/HDD background I/O and cache effects",
         "Three sessions per pause; descriptive statistics only"]}
    (output/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    rows=[]
    try:
        for job in jobs:
            start=time.perf_counter_ns()
            with open(r"\\.\PhysicalDrive2","rb",buffering=0) as device:
                open_ms=(time.perf_counter_ns()-start)/1_000_000
                if job["pause_after_open_s"]:
                    time.sleep(job["pause_after_open_s"])
                first_ms=single_read(device,job["first_offset"])
                second_ms=single_read(device,job["second_offset"])
                rows.append({**job,"open_ms":round(open_ms,5),
                    "first_read_ms":round(first_ms,5),
                    "second_read_ms":round(second_ms,5)})
            print(f"session {job['session']}/{len(jobs)} complete; idle={job['pause_after_open_s']} s")
    except OSError as err:
        if rows:csv_write(output/"observations_partial.csv",rows)
        (output/"error.txt").write_text(str(err),encoding="utf-8")
        raise RuntimeError("Read aborted; no permission bypass or retries. Output: "+str(output)) from err
    csv_write(output/"observations.csv",rows)
    summary=[]
    for delay in PAUSES:
        sub=[r for r in rows if r["pause_after_open_s"]==delay]
        summary.append({"pause_after_open_s":delay,"sessions":len(sub),
          "median_open_ms":round(statistics.median(r["open_ms"] for r in sub),5),
          "median_first_ms":round(statistics.median(r["first_read_ms"] for r in sub),5),
          "median_second_ms":round(statistics.median(r["second_read_ms"] for r in sub),5),
          "slow_first_over_200ms":sum(r["first_read_ms"]>200 for r in sub)})
    csv_write(output/"summary.csv",summary)
    manifest["status"]="complete"
    (output/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print("SUCCESS:",output)
    print("Measured first-read association only; NOT confirmed disk spin-up or Zebra placement speedup.")
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
    p.add_argument("--seed",type=int,default=20261113)
    a=p.parse_args()
    try:
        validate_hgst(a)
        jobs=plan(a.seed)
        if not a.run:
            print("PLAN ONLY — NO device opens, Windows queries, disk reads, sleeps or new files.")
            print(json.dumps({"device":"HGST Disk 2 / T: NTFS (live identity must be checked)",
                "sessions":len(jobs),"reads":len(jobs)*2,
                "total_read_bytes":len(jobs)*2*BLOCK,
                "pauses_seconds":list(PAUSES),
                "repetitions_per_pause":REPETITIONS,
                "jobs":jobs,"write_to_T":False},ensure_ascii=False,indent=2))
            return 0
        return execute(a,jobs)
    except (ValueError,RuntimeError,OSError) as exc:
        print("ERROR:",exc,file=sys.stderr);return 1

if __name__=="__main__":raise SystemExit(main())
