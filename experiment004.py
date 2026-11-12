#!/usr/bin/env python3
"""Experiment 004: constrained read-only HGST USB bridge comparison run.

Never writes to the physical drive; only stores results inside F:/zebra-ganta_ch2/results.
It does not infer physical seek times, USB link speeds, or algorithm gains.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import sys
from lab import EXPECTED_TARGET, DEFAULT_SIZE, MIB, inventory, normalize_model, offsets, read_exact, powershell_json
from transitions import BLOCK, plan, single_read

ROOT = Path(__file__).resolve().parent
LABELS = ("usb2-jmicron", "usb3-orico")
def verify(args):
    matches = [d for d in inventory() if int(d["Number"]) == args.disk]
    if len(matches) != 1: raise RuntimeError("Disk number missing or ambiguous")
    d = matches[0]
    model = str(d.get("Model") or "") + " " + str(d.get("FriendlyName") or "")
    if normalize_model(EXPECTED_TARGET) not in normalize_model(model):
        raise RuntimeError("Disk model not matched (may be hidden by bridge); no reads: "+model)
    if int(d["Size"]) != DEFAULT_SIZE or int(d["Size"]) != args.size:
        raise RuntimeError("Get-Disk byte size differs from verified reference")
    if int(d.get("Win32Size") or 0) != args.win32_size:
        raise RuntimeError("Win32_DiskDrive byte size differs from expressly confirmed value")
    if str(d.get("BusType")).upper() != "USB" or d.get("IsSystem") or d.get("IsBoot") or d.get("IsOffline"):
        raise RuntimeError("Unsafe or non-USB disk; no reads")
    if str(d.get("OperationalStatus","")).lower() != "online":
        raise RuntimeError("Disk not online")
    ps = "$x=@(Get-Partition -DiskNumber "+str(args.disk)+" | Where-Object {$_.DriveLetter} | ForEach-Object { $_.DriveLetter.ToString() }); ConvertTo-Json -InputObject $x -Compress"
    letters=powershell_json(ps)
    if not isinstance(letters,list): letters=[letters] if letters else []
    if args.letter.upper() not in [str(x).upper() for x in letters]:
        raise RuntimeError("Expected drive letter missing; got "+repr(letters))
    return d

def save_csv(path,rows):
    if not rows: raise RuntimeError("No rows produced")
    with path.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def run(args):
    if os.name!="nt":raise RuntimeError("Native Windows only")
    if ROOT.drive.upper()!="F:" or ROOT.name.lower()!="zebra-ganta_ch2":
        raise RuntimeError("Run script only from F:\\zebra-ganta_ch2; results must stay on F:")
    if len(args.letter)!=1 or not args.letter.isascii() or not args.letter.isalpha():
        raise RuntimeError("Invalid drive letter")
    if args.letter.upper()=="F":raise RuntimeError("Test disk letter must not be project drive F:")
    if not (args.bridge in LABELS):raise RuntimeError("Unknown bridge label")
    if args.mib!=16 or args.samples not in (5,21) or args.repeats!=3 or args.pairs not in (20,40):
        raise RuntimeError("Comparable protocol parameters required: 16MiB, 5/21 zones, 3 repeats, 20/40 pairs")
    disk=verify(args)
    path=r"\\.\PhysicalDrive"+str(args.disk)
    print("READ-ONLY TARGET:",json.dumps(disk,ensure_ascii=False))
    print("EXPECTED PARTITION LETTER:",args.letter.upper()+":")
    print("BRIDGE:",args.bridge,"USBView negotiated mode (operator note):",args.link_speed)
    print("Destination: F:\\zebra-ganta_ch2\\results (NOT test disk)")
    print("Two test stages: sequential zone reads, near/far paired 4KiB reads.")
    phrase="READ HGST DISK "+str(args.disk)
    if input("Type "+repr(phrase)+" to confirm: ").strip()!=phrase:
        raise RuntimeError("Cancelled")
    if verify(args)!=disk: raise RuntimeError("Device identity changed before open")
    output=ROOT/"results"/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-exp004-"+args.bridge)
    output.mkdir(parents=True,exist_ok=False)
    manifest={"schema":"zebra-ganta.exp004.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),
      "bridge":args.bridge,"reported_dock":"ORICO 6139C3-EU-CR-BP" if args.bridge=="usb3-orico" else "JMicron VID 152D PID 2338",
      "reported_cable":"USB-C to USB-C" if args.bridge=="usb3-orico" else "old adapter cable",
      "reported_power":"separate 12V dock power" if args.bridge=="usb3-orico" else "unspecified",
      "usbview_negotiated_link_speed_manual":args.link_speed,"usbview_vidpid_manual":args.vidpid,
      "disk":disk,"letter":args.letter.upper(),"disk_number":args.disk,"win32_size_expected":args.win32_size,
      "scan_samples":args.samples,"scan_mib":args.mib,"scan_repeats":args.repeats,
      "transition_pairs":args.pairs,"seed":args.seed,
      "limits":["Windows+USB latency, not isolated head seek","cache not isolated",
       "USBView notes manually entered; not cross-checked by this program","no inference of HDD optimization speedup"]}
    (output/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    seq=[]; paired=[]
    try:
        with open(path,"rb",buffering=0) as handle:
            zones=offsets(args.size,args.samples,args.mib*MIB)
            for repeat in range(1,args.repeats+1):
                order=zones if repeat%2 else list(reversed(zones))
                for pos,off in order:
                    secs=read_exact(handle,off,args.mib*MIB)
                    seq.append({"repeat":repeat,"position_percent":pos,"offset_bytes":off,
                      "read_bytes":args.mib*MIB,"seconds":round(secs,7),
                      "MB_s":round(args.mib*MIB/secs/1_000_000,3)})
            jobs=plan(args.size,args.pairs,args.seed)
            for i,(home,near,far) in enumerate(jobs):
                modes=[("near",near),("far",far)] if i%2==0 else [("far",far),("near",near)]
                for name,target in modes:
                    anchor_ms=single_read(handle,home)
                    latency_ms=single_read(handle,target)
                    paired.append({"pair":i+1,"mode":name,"anchor_offset":home,
                      "target_offset":target,"distance_bytes":abs(target-home),
                      "anchor_ms":round(anchor_ms,5),"target_read_ms":round(latency_ms,5),"bytes":BLOCK})
    except (OSError,PermissionError) as e:
        (output/"error.txt").write_text(str(e),encoding="utf-8")
        raise RuntimeError("Read failed; no retry or security bypass. See "+str(output/"error.txt")) from e
    save_csv(output/"measurements.csv",seq)
    save_csv(output/"observations.csv",paired)
    summary=[]
    for pos,_ in zones:
        values=[row["MB_s"] for row in seq if row["position_percent"]==pos]
        summary.append({"position_percent":pos,"median_MB_s":round(statistics.median(values),3),
          "min_MB_s":min(values),"max_MB_s":max(values),"repeat_count":len(values)})
    save_csv(output/"summary.csv",summary)
    print("SUCCESS: real read-only measurements saved:",output)
    print("Reported USB link speed remains a manual USBView field, not automatically measured.")
    return 0

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--disk",type=int,required=True)
    p.add_argument("--letter",required=True,help="Verified current drive letter, without colon")
    p.add_argument("--size",type=int,required=True,help="Verified Get-Disk.Size, must equal documented HGST")
    p.add_argument("--win32-size",type=int,required=True,help="Win32_DiskDrive.Size for CURRENT adapter")
    p.add_argument("--bridge",choices=LABELS,required=True)
    p.add_argument("--link-speed",choices=["High","Super","SuperPlus","Unknown"],required=True)
    p.add_argument("--vidpid",required=True,help="USBView VID:PID manually recorded")
    p.add_argument("--samples",type=int,default=5)
    p.add_argument("--mib",type=int,default=16)
    p.add_argument("--repeats",type=int,default=3)
    p.add_argument("--pairs",type=int,default=20)
    p.add_argument("--seed",type=int,default=20261112)
    a=p.parse_args()
    try:return run(a)
    except (RuntimeError,ValueError,OSError) as e:
        print("ERROR:",e,file=sys.stderr);return 1
if __name__=="__main__":raise SystemExit(main())
