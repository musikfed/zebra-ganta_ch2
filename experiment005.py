#!/usr/bin/env python3
r"""Experiment 005: counterbalanced read-only near/far HDD latency.

By default this prints a deterministic plan and DOES NOT open a physical drive.
Live operation requires --run, full disk identity confirmation, and explicit phrase.
Results are written ONLY to F:\zebra-ganta_ch2\results, never to the HGST volume.
This is NOT an isolated physical head-seek measurement.
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

from experiment004 import verify
from lab import DEFAULT_SIZE
from transitions import BLOCK, MIN_GAP, plan, single_read

ROOT = Path(__file__).resolve().parent
DEFAULT_PAIRS = 20
ROUNDS = (("near", "far"), ("far", "near"), ("far", "near"), ("near", "far"))


def schedule(pairs: int = DEFAULT_PAIRS, seed: int = 20261112):
    """ABBA per address pair: both near/far orders for the SAME addresses."""
    if pairs not in (20, 40):
        raise ValueError("Only 20 or 40 address pairs are allowed")
    result = []
    for pair_id, (anchor, near, far) in enumerate(plan(DEFAULT_SIZE, pairs, seed), 1):
        for round_no, modes in enumerate(ROUNDS, 1):
            for slot, mode in enumerate(modes, 1):
                target = near if mode == "near" else far
                if not (BLOCK <= anchor < DEFAULT_SIZE-BLOCK
                        and BLOCK <= target < DEFAULT_SIZE-BLOCK
                        and anchor % BLOCK == target % BLOCK == 0):
                    raise ValueError("Unsafe or unaligned planned offset")
                result.append({"pair": pair_id, "round": round_no, "slot": slot,
                    "mode": mode, "anchor_offset": anchor,
                    "target_offset": target, "distance_bytes": abs(target-anchor)})
    return result


def write_csv(dest: Path, rows: list[dict]):
    if not rows:
        raise ValueError("No rows to write")
    with dest.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def validate_args(args):
    if args.disk < 0 or args.size != DEFAULT_SIZE:
        raise RuntimeError("Invalid disk number or documented HGST capacity")
    if args.win32_size != 500105249280:
        raise RuntimeError("Win32 HGST capacity mismatch; no read permitted")
    if args.letter.upper() != "T":
        raise RuntimeError("This physical experiment requires verified T: HGST volume")
    if args.bridge != "usb3-orico" or args.vidpid.upper() != "2109:0715":
        raise RuntimeError("Only documented ORICO VIA Labs 2109:0715 test setup is permitted")
    if args.link_speed != "Super":
        raise RuntimeError("The documented connection must be SuperSpeed in USBView")
    if args.pairs not in (20, 40):
        raise RuntimeError("Only bounded 20 or 40-pair measurements are permitted")


def check_usb_parent(args):
    """Confirm VIA USB parent of the exact WMI disk; no raw sectors accessed."""
    from lab import powershell_json
    ps = (
        "$w=Get-CimInstance Win32_DiskDrive -Filter 'Index="+str(args.disk)+"';"
        "if(!$w){throw 'Missing WMI disk'};"
        "$cur=[string]$w.PNPDeviceID;$anc=@();"
        "for($i=0;$i -lt 10 -and $cur;$i++){"
        "$anc+= $cur;"
        "try {$p=Get-PnpDeviceProperty -InstanceId $cur -KeyName DEVPKEY_Device_Parent -ErrorAction Stop} "
        "catch {break};"
        "$n=[string]$p.Data;if(!$n -or $n -eq $cur){break};$cur=$n"
        "};ConvertTo-Json -InputObject $anc -Compress"
    )
    ancestors = powershell_json(ps)
    if isinstance(ancestors, str):
        ancestors = [ancestors]
    if not isinstance(ancestors, list) or not any(
        x.upper().startswith("USB\\VID_2109&PID_0715\\") for x in ancestors
        if isinstance(x, str)
    ):
        raise RuntimeError("HGST PnP ancestor chain does not contain VIA Labs VID_2109&PID_0715")
    return ancestors


def run_live(args, jobs):
    if os.name != "nt":
        raise RuntimeError("Live experiment is only available on native Windows")
    if ROOT.drive.upper() != "F:" or ROOT.name.lower() != "zebra-ganta_ch2":
        raise RuntimeError("Repository must be at F:\\zebra-ganta_ch2")
    validate_args(args)
    original = verify(args)
    ancestors = check_usb_parent(args)
    print("Verified:",json.dumps(original,ensure_ascii=False))
    print("PnP ancestor:",next(x for x in ancestors if x.upper().startswith("USB\\VID_2109&PID_0715\\")))
    print("Read-only physical disk: \\\\.\\PhysicalDrive"+str(args.disk))
    print("Total target reads:",len(jobs)," + same number of 4 KiB anchor reads")
    print("Results ONLY under F:\\zebra-ganta_ch2\\results")
    print("All 4 rounds on same LBA locations; repeated data may be cached.")
    phrase="READ HGST DISK "+str(args.disk)+" EXP005"
    if input("Type "+repr(phrase)+" to proceed: ").strip()!=phrase:
        raise RuntimeError("Cancelled without raw reads")
    if verify(args) != original or check_usb_parent(args) != ancestors:
        raise RuntimeError("Hardware identity changed after confirmation")
    target = ROOT/"results"/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-exp005-orico")
    target.mkdir(parents=True,exist_ok=False)
    manifest = {"schema":"zebra-ganta.exp005.v1","created_utc":datetime.now(timezone.utc).isoformat(),
        "status":"incomplete","source":"real Windows raw read-only",
        "disk":original,"pnp_ancestors":ancestors,"bridge":args.bridge,
        "usbview_vidpid_operator":args.vidpid,"usbview_link_speed_operator":args.link_speed,
        "pairs":args.pairs,"seed":args.seed,"rounds":"ABBA; near-far / far-near / far-near / near-far",
        "sample_block_bytes":BLOCK,"near_distance_bytes":MIN_GAP,
        "limitations":["Read-only Windows + USB latency, not pure seek time",
            "Repeated LBA blocks can be cached by Windows, bridge or HDD",
            "Physical radius unknown and near/far zones differ",
            "ABBA balances order but does not eliminate warmup and cache effects",
            "Operator must compare any new result to exp003/004 without speedup claims"]}
    (target/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    rows = []
    try:
        with open(r"\\.\PhysicalDrive"+str(args.disk),"rb",buffering=0) as handle:
            for job in jobs:
                anchor_ms=single_read(handle,job["anchor_offset"])
                latency_ms=single_read(handle,job["target_offset"])
                rows.append({**job,"anchor_ms":round(anchor_ms,5),
                    "target_read_ms":round(latency_ms,5),"bytes":BLOCK})
                if len(rows)%40==0:
                    print("completed",len(rows),"/",len(jobs),"target samples")
    except (OSError,PermissionError) as exc:
        if rows:
            write_csv(target/"observations_partial.csv",rows)
        (target/"error.txt").write_text(str(exc),encoding="utf-8")
        print("PARTIAL/FAILED; see",target,file=sys.stderr)
        return 2
    write_csv(target/"observations.csv",rows)
    manifest["status"]="complete"
    (target/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    near = [r["target_read_ms"] for r in rows if r["mode"]=="near"]
    far = [r["target_read_ms"] for r in rows if r["mode"]=="far"]
    print("Measured (Windows+USB, NOT physical seek): near median",round(statistics.median(near),4),
        "ms; far median",round(statistics.median(far),4),"ms")
    print("SUCCESS:",target)
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run",action="store_true",help="Actually perform guarded read-only HDD measurements; default PLAN ONLY")
    p.add_argument("--disk",type=int,default=2)
    p.add_argument("--letter",default="T")
    p.add_argument("--size",type=int,default=DEFAULT_SIZE)
    p.add_argument("--win32-size",type=int,default=500105249280)
    p.add_argument("--bridge",default="usb3-orico")
    p.add_argument("--link-speed",default="Super")
    p.add_argument("--vidpid",default="2109:0715")
    p.add_argument("--pairs",type=int,default=20)
    p.add_argument("--seed",type=int,default=20261112)
    a = p.parse_args()
    try:
        validate_args(a)
        jobs = schedule(a.pairs,a.seed)
        if not a.run:
            print("PLAN ONLY — no hardware queried, no files created, no physical reads.")
            print(json.dumps({"pairs":a.pairs,"rounds_per_pair":4,
                 "slots_per_round":2,"target_reads":len(jobs),
                 "anchor_reads":len(jobs),"bytes_per_read":BLOCK,
                 "first_8_jobs":jobs[:8]},ensure_ascii=False,indent=2))
            return 0
        return run_live(a,jobs)
    except (RuntimeError,ValueError,OSError) as exc:
        print("ERROR:",exc,file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
