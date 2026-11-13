#!/usr/bin/env python3
r"""Experiment 010: first-read overhead versus pause AFTER opening a raw HDD handle.

Physical HGST 2.5in Disk 2, T: NTFS, ORICO VIA 2109:0715 SuperSpeed.
PLAN ONLY by default. Live: 9 short read-only sessions (18 x 4 KiB total);
no spin-down commands, USB unplug, power management, formatting or T: writes.
Separates handle opening duration, wait, first read and second distinct read.
Measured effect is Windows+USB+HDD path, NOT proven spindle startup.
"""
from __future__ import annotations
import argparse,csv,json,os,random,statistics,sys,time
from datetime import datetime,timezone
from pathlib import Path
from experiment004 import verify
from experiment005 import check_usb_parent
from experiment008 import validate as validate_hgst, verify_ntfs
from lab import DEFAULT_SIZE
from transitions import BLOCK,single_read

ROOT=Path(__file__).resolve().parent
PAUSES=(0,2,10)
SESSIONS=9
GAP=2*1024*1024

def schedule(seed=20261113):
    """Each pause condition 3x in shuffled order, unique aligned LBA ranges."""
    if not isinstance(seed,int) or seed<0 or seed>2**32-1:
        raise ValueError("Seed out of bounded range")
    rng=random.Random(seed)
    pauses=list(PAUSES)*3
    rng.shuffle(pauses)
    seen=set()
    sessions=[]
    for i,secs in enumerate(pauses,1):
        # Independently sampled addresses 10-90% logical surface.
        # Second request is 2MiB away and not the same block.
        start=((int(DEFAULT_SIZE*(0.1+0.8*rng.random())))//BLOCK)*BLOCK
        for offset in (start,start+GAP):
            if offset<BLOCK or offset+BLOCK>=DEFAULT_SIZE or offset in seen:
                raise ValueError("Invalid, duplicate or out-of-bounds physical offset")
            seen.add(offset)
        sessions.append({"session":i,"pause_after_open_s":secs,
                         "first_offset":start,"second_offset":start+GAP,
                         "read_bytes":BLOCK})
    if len(seen)!=SESSIONS*2 or any(pauses.count(x)!=3 for x in PAUSES):
        raise AssertionError("Unbalanced plan")
    return sessions

def write_csv(path,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def execute(args,jobs):
    if os.name!="nt" or ROOT.drive.upper()!="F:" or ROOT.name.lower()!="zebra-ganta_ch2":
        raise RuntimeError("Native Windows project F:\\zebra-ganta_ch2 required")
    validate_hgst(args)
    disk=verify(args)
    ntfs=verify_ntfs(args)
    ancestors=check_usb_parent(args)
    print("Verified HGST:",json.dumps(disk,ensure_ascii=False))
    print("Verified volume:",ntfs,"USB PnP VIA 2109:0715")
    print("9 sessions, 18 unique raw 4KiB reads, no writes to T:; results only on F:")
    print("Pause after opening handle is NOT spindle spin-down control.")
    phrase="READ HGST DISK 2 EXP010"
    if input("Type "+repr(phrase)+" to run: ").strip()!=phrase:
        raise RuntimeError("Cancelled")
    if verify(args)!=disk or verify_ntfs(args)!=ntfs or check_usb_parent(args)!=ancestors:
        raise RuntimeError("Disk/volume/USB identity changed; stop")
    folder=ROOT/"results"/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-exp010-startup-ntfs")
    folder.mkdir(parents=True,exist_ok=False)
    manifest={"schema":"zebra-ganta.exp010.v1","status":"incomplete",
        "created_utc":datetime.now(timezone.utc).isoformat(),"seed":args.seed,
        "read_only":True,"disk":disk,"volume":ntfs,"pnp_parent":"VIA Labs 2109:0715",
        "pauses_after_handle_open_s":PAUSES,"sessions":SESSIONS,"reads_per_session":2,
        "block_bytes":BLOCK,"limitations":[
          "Windows/USB/HDD time; no direct spindle or servo telemetry",
          "Wait after handle open, no controlled disk sleep or spin-down",
          "First and second requests use different LBA, radial position not identical",
          "Potential cache, Windows background I/O, temperature or link-state effects",
          "Only 3 sessions per pause; not a basis for general causal claims"]}
    (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    rows=[]
    try:
        for j in jobs:
            begin=time.perf_counter_ns()
            with open(r"\\.\PhysicalDrive2","rb",buffering=0) as handle:
                open_ms=(time.perf_counter_ns()-begin)/1_000_000
                if j["pause_after_open_s"]:
                    time.sleep(j["pause_after_open_s"])
                first_ms=single_read(handle,j["first_offset"])
                second_ms=single_read(handle,j["second_offset"])
                rows.append({**j,"open_ms":round(open_ms,5),
                   "first_read_ms":round(first_ms,5),"second_read_ms":round(second_ms,5)})
            print("completed",j["session"],"/9, pause",j["pause_after_open_s"],"s")
    except (OSError,PermissionError) as e:
        if rows:write_csv(folder/"observations_partial.csv",rows)
        (folder/"error.txt").write_text(str(e),encoding="utf-8")
        raise RuntimeError("Raw read failed; no retries or permission bypass: "+str(folder)) from e
    write_csv(folder/"observations.csv",rows)
    summary=[]
    for secs in PAUSES:
        sub=[x for x in rows if x["pause_after_open_s"]==secs]
        summary.append({"pause_after_open_s":secs,"sessions":len(sub),
           "median_open_ms":round(statistics.median(x["open_ms"] for x in sub),5),
           "median_first_ms":round(statistics.median(x["first_read_ms"] for x in sub),5),
           "median_second_ms":round(statistics.median(x["second_read_ms"] for x in sub),5)})
    write_csv(folder/"summary.csv",summary)
    manifest["status"]="complete"
    (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print("SUCCESS:",folder)
    print("NOT spindle wakeup proof: pause is after opening handle and sessions are short.")
    return 0

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run",action="store_true")
    ap.add_argument("--disk",type=int,default=2)
    ap.add_argument("--letter",default="T")
    ap.add_argument("--size",type=int,default=DEFAULT_SIZE)
    ap.add_argument("--win32-size",type=int,default=500105249280)
    ap.add_argument("--bridge",default="usb3-orico")
    ap.add_argument("--vidpid",default="2109:0715")
    ap.add_argument("--link-speed",default="Super")
    ap.add_argument("--seed",type=int,default=20261113)
    args=ap.parse_args()
    try:
        validate_hgst(args)
        jobs=schedule(args.seed)
        if not args.run:
            print("PLAN ONLY — NO physical disk access, Windows query, read, sleep or file creation.")
            print(json.dumps({"target":"HGST Disk 2 / NTFS T:, to be verified in live mode",
                "sessions":len(jobs),"reads":18,"total_read_bytes":18*BLOCK,
                "pauses_s":list(PAUSES),"jobs":jobs,"write_to_T":False},ensure_ascii=False,indent=2))
            return 0
        return execute(args,jobs)
    except (ValueError,RuntimeError,OSError) as e:
        print("ERROR:",e,file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
