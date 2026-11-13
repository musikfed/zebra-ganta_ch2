#!/usr/bin/env python3
r"""Experiment 008: cumulative LBA access-order cost on a REAL 2.5" HGST HDD.

Volume T: must be NTFS. Raw reads are read-only. No ext4, Linux, formatting
or file placement involved. Default PLAN ONLY does not access the disk.
This compares scheduling of logical reads, NOT on-media Zebra layouts.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import statistics
import sys
import time

from experiment004 import verify
from experiment005 import check_usb_parent
from lab import DEFAULT_SIZE, powershell_json
from transitions import BLOCK, single_read

ROOT = Path(__file__).resolve().parent
WIN32_SIZE = 500105249280
EXPECTED_PNP = "2109:0715"

def plan(seed: int = 20261113, count: int = 128, traces: int = 4):
    """Disjoint, aligned addresses, stratified across disk, no address repeats.

    Two distinct traces per comparison use matched radial distributions to
    minimize cross-run cache warming. Assign ordered/shuffled in AB/BA order.
    This is NOT exactly the same LBA set per mode: report this limitation.
    """
    if count not in (64, 128, 256) or traces not in (4, 8):
        raise ValueError("Only count 64/128/256 and 4/8 traces supported")
    rng = random.Random(seed)
    used = set()
    out = []
    for t in range(traces):
        addresses=[]
        for i in range(count):
            # Radial strata 5-95%; independently jittered within each stratum.
            percent = 0.05 + 0.90*(i + (0.15+0.70*rng.random()))/count
            offset = (int(DEFAULT_SIZE*percent)//BLOCK)*BLOCK
            while offset in used:
                offset += BLOCK
            if offset < BLOCK or offset + BLOCK >= DEFAULT_SIZE:
                raise ValueError("Read offset outside device")
            used.add(offset)
            addresses.append(offset)
        mode = "ordered" if t % 4 in (0,3) else "shuffled"
        addresses.sort()
        if mode=="shuffled":
            rng.shuffle(addresses)
        out.append({"trace":t+1,"mode":mode,"offsets":addresses})
    if sum(len(x["offsets"]) for x in out)!=len(used):
        raise AssertionError("Repeated LBA read planned")
    return out

def verify_ntfs(args):
    """Confirm T: belongs to Disk N and is NTFS, without file operations."""
    ps = (
        "$ErrorActionPreference='Stop';"
        "$p=Get-Partition -DriveLetter T -ErrorAction Stop;"
        "$v=Get-Volume -DriveLetter T -ErrorAction Stop;"
        "[PSCustomObject]@{DiskNumber=[int]$p.DiskNumber;"
        "FileSystem=[string]$v.FileSystem;DriveLetter=[string]$p.DriveLetter}"
        "|ConvertTo-Json -Compress")
    d=powershell_json(ps)
    if not isinstance(d,dict) or d.get("DiskNumber")!=args.disk or str(d.get("FileSystem","")).upper()!="NTFS" or str(d.get("DriveLetter","")).upper()!="T":
        raise RuntimeError("HGST T: must be confirmed NTFS on selected Disk N")
    return d

def validate(args):
    if args.disk!=2 or args.letter.upper()!="T" or args.size!=DEFAULT_SIZE or args.win32_size!=WIN32_SIZE:
        raise RuntimeError("Only documented HGST disk 2 / NTFS T: / known sizes accepted")
    if args.bridge!="usb3-orico" or args.vidpid.upper()!=EXPECTED_PNP or args.link_speed!="Super":
        raise RuntimeError("Only documented ORICO/VIA SuperSpeed configuration permitted")

def write_rows(path,rows):
    if not rows:return
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)

def execute(args,traces):
    if os.name!="nt" or ROOT.drive.upper()!="F:" or ROOT.name.lower()!="zebra-ganta_ch2":
        raise RuntimeError("Native Windows at F:\\zebra-ganta_ch2 required")
    validate(args)
    disk=verify(args)
    volume=verify_ntfs(args)
    parents=check_usb_parent(args)
    print("VERIFIED:",json.dumps({"disk":disk,"volume":volume,"usb_parent_confirmed":EXPECTED_PNP},ensure_ascii=False))
    print("READ ONLY: PhysicalDrive2; NTFS T: is identified but not modified.")
    print("No files created on T:; trace observations ONLY on F:.")
    print("Unique address across ALL traces; two distinct address sets in each mode.")
    phrase="READ HGST DISK 2 EXP008"
    if input("Type "+repr(phrase)+": ").strip()!=phrase:
        raise RuntimeError("Cancelled before device read")
    if verify(args)!=disk or verify_ntfs(args)!=volume or check_usb_parent(args)!=parents:
        raise RuntimeError("Device identity changed; stop")
    result=ROOT/"results"/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-exp008-ntfs-hgst")
    result.mkdir(parents=True,exist_ok=False)
    manifest={
      "schema":"zebra-ganta.exp008.v1","status":"incomplete",
      "kind":"REAL HDD read-only access-order experiment",
      "time_utc":datetime.now(timezone.utc).isoformat(),"disk":disk,"volume":volume,
      "usb_bridge":"ORICO VIA Labs 2109:0715, 5 Gbit/s operator-confirmed USBView",
      "count_per_trace":args.count,"traces":args.traces,"seed":args.seed,
      "block_bytes":BLOCK,"no_duplicate_LBA":True,"format":"NTFS on existing T:",
      "limitations":[
        "Different, radially matched LBA sets for ordered and shuffled traces to avoid cross-mode cache reuse",
        "Address distributions matched approximately, not identical; this can confound effects",
        "Windows USB and HDD cache still may affect timings",
        "No direct head seek telemetry and no on-disk file layout change",
        "Access-order effect is NOT proof of Zebra placement acceleration"]}
    (result/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    rows=[]; summaries=[]
    try:
        with open(r"\\.\PhysicalDrive2","rb",buffering=0) as h:
            for tr in traces:
                start=time.perf_counter_ns()
                last=None
                for j,offset in enumerate(tr["offsets"],1):
                    latency=single_read(h,offset)
                    rows.append({"trace":tr["trace"],"mode":tr["mode"],"sequence":j,
                        "offset_bytes":offset,"jump_bytes":0 if last is None else abs(offset-last),
                        "read_bytes":BLOCK,"target_read_ms":round(latency,5)})
                    last=offset
                end=time.perf_counter_ns()
                subset=[r for r in rows if r["trace"]==tr["trace"]]
                summaries.append({"trace":tr["trace"],"mode":tr["mode"],
                    "reads":len(subset),"total_wall_ms":round((end-start)/1_000_000,5),
                    "median_read_ms":round(statistics.median(r["target_read_ms"] for r in subset),5),
                    "jump_sum_bytes":sum(r["jump_bytes"] for r in subset)})
                print("trace",tr["trace"],tr["mode"],"completed",len(subset),"reads")
    except (OSError,PermissionError) as exc:
        write_rows(result/"observations_partial.csv",rows)
        (result/"error.txt").write_text(str(exc),encoding="utf-8")
        raise RuntimeError("Physical read failed; no retries or bypass. "+str(result)) from exc
    write_rows(result/"observations.csv",rows)
    write_rows(result/"summary.csv",summaries)
    manifest["status"]="complete"
    (result/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print("SUCCESS:",result)
    print("Observed Windows+USB access ordering; NOT a proven filesystem placement acceleration.")
    return 0

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run",action="store_true")
    ap.add_argument("--disk",type=int,default=2)
    ap.add_argument("--letter",default="T")
    ap.add_argument("--size",type=int,default=DEFAULT_SIZE)
    ap.add_argument("--win32-size",type=int,default=WIN32_SIZE)
    ap.add_argument("--bridge",default="usb3-orico")
    ap.add_argument("--vidpid",default=EXPECTED_PNP)
    ap.add_argument("--link-speed",default="Super")
    ap.add_argument("--count",type=int,default=128)
    ap.add_argument("--traces",type=int,default=4)
    ap.add_argument("--seed",type=int,default=20261113)
    args=ap.parse_args()
    try:
        validate(args)
        traces=plan(args.seed,args.count,args.traces)
        if not args.run:
            print("PLAN ONLY. NO disk access; NO disk reads; NO files created.")
            print(json.dumps({"device":"HGST 2.5in Disk 2, T: NTFS (must be verified if --run)",
                "traces":[{"trace":t["trace"],"mode":t["mode"],"reads":len(t["offsets"]),
                  "first_3_offsets":t["offsets"][:3]} for t in traces],
                "total_unique_reads":sum(len(t["offsets"]) for t in traces),
                "write_to_T":False},ensure_ascii=False,indent=2))
            return 0
        return execute(args,traces)
    except (ValueError,RuntimeError,OSError) as exc:
        print("ERROR:",exc,file=sys.stderr);return 1

if __name__=="__main__":
    raise SystemExit(main())
