#!/usr/bin/env python3
r"""Experiment 008: cumulative cost of LBA traversal, extending experiment 003.

PLAN ONLY by default: no inventory, file access, device I/O or output files.
--run: bounded READ-ONLY 4 KiB reads from verified HGST T: / Disk 2 via USB.
Writes observations exclusively to F:\zebra-ganta_ch2\results.

Each profile uses distinct, never-repeated target LBAs. Sampling is matched
by LBA region and offset distributions, but NOT identical addresses. This
reduces exact-address cache confounding found in experiment 005 without
eliminating Windows/USB/HDD caching, read-ahead, rotational or scheduler effects.
No physical track geometry or head-seek time can be inferred from these reads.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parent
SIZE = 500_106_780_160
WIN32_SIZE = 500_105_249_280
BLOCK = 4096
MIB = 1024 * 1024
ROUNDS = 3
ZONES = 8
MODES = ("sequential", "alternating", "shuffled")
ALLOWED_BLOCKS_PER_ZONE = (8, 16, 32)


def validate_args(args):
    """Reject any setup outside the recorded HGST/ORICO test bench."""
    if (args.disk != 2 or args.letter != "T" or args.size != SIZE
            or args.win32_size != WIN32_SIZE or args.bridge != "usb3-orico"
            or args.vidpid.upper() != "2109:0715" or args.link_speed != "Super"):
        raise ValueError("Only verified HGST Disk 2 / T: / ORICO SuperSpeed is allowed")
    if args.blocks_per_zone not in ALLOWED_BLOCKS_PER_ZONE:
        raise ValueError("blocks-per-zone must be 8, 16 or 32")
    if not 0 <= args.seed <= 2**32 - 1:
        raise ValueError("seed must fit unsigned 32-bit integer")


def traversal(addresses, mode, seed):
    """Same requested address distribution within each profile, different order."""
    ordered = sorted(addresses, key=lambda x: x[0])
    if mode == "sequential":
        return ordered
    if mode == "alternating":
        result = []
        left, right = 0, len(ordered)-1
        while left <= right:
            result.append(ordered[left])
            if left != right:
                result.append(ordered[right])
            left += 1
            right -= 1
        return result
    if mode == "shuffled":
        result = ordered.copy()
        random.Random(seed).shuffle(result)
        return result
    raise ValueError("Unknown traversal mode")


def build_plan(blocks_per_zone=16, seed=20261113):
    """3 counterbalanced rounds; disjoint 4 KiB targets with 1 MiB spacing.

    Three modes sample adjacent but nonidentical offset lanes in each of eight
    widely separated LBA regions. Latin-square order rotates across rounds.
    """
    if blocks_per_zone not in ALLOWED_BLOCKS_PER_ZONE:
        raise ValueError("Unsafe sample size")
    if not 0 <= seed <= 2**32 - 1:
        raise ValueError("Invalid random seed")
    out = []
    for round_idx in range(ROUNDS):
        order = MODES[round_idx:] + MODES[:round_idx]
        for slot, mode in enumerate(order, 1):
            lane = (MODES.index(mode) + round_idx) % len(MODES)
            addresses = []
            for zone in range(ZONES):
                base = int(SIZE * (0.10 + 0.80 * zone / (ZONES - 1)))
                base = base // BLOCK * BLOCK
                for index in range(blocks_per_zone):
                    # Nine mutually disjoint lanes; adjacent sampled addresses
                    # within a mode are 9 MiB apart to reduce read-ahead bias.
                    cell = index * (ROUNDS * len(MODES)) + round_idx * len(MODES) + lane
                    offset = base + cell * MIB
                    if offset % BLOCK or not BLOCK <= offset <= SIZE - BLOCK:
                        raise ValueError("Unsafe physical disk offset")
                    addresses.append((offset, zone + 1))
            ordered = traversal(addresses, mode, seed + 1009 * round_idx)
            previous = None
            for step, (offset, zone) in enumerate(ordered, 1):
                out.append({
                    "round": round_idx + 1, "slot": slot, "mode": mode,
                    "step": step, "zone": zone, "offset_bytes": offset,
                    "distance_from_previous_bytes": (
                        None if previous is None else abs(offset - previous)),
                    "read_bytes": BLOCK,
                })
                previous = offset
    if len(set(row["offset_bytes"] for row in out)) != len(out):
        raise ValueError("Target addresses are not globally unique")
    return out


def percentile(values, q):
    """Linear percentile; q in [0, 1]."""
    if not values or not 0 <= q <= 1:
        raise ValueError("Cannot calculate percentile")
    a = sorted(values)
    i = (len(a) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return a[lo] + (a[hi] - a[lo]) * (i - lo)


def summarize(rows, durations_ms, blocks_per_zone):
    """Summaries of actual observations, never of generated plans."""
    expected = ZONES * blocks_per_zone
    report = []
    seen = set()
    for trial in range(1, ROUNDS + 1):
        for mode in MODES:
            key = (trial, mode)
            r = [x for x in rows if (x["round"], x["mode"]) == key]
            if len(r) != expected or key not in durations_ms:
                raise ValueError("Incomplete trial")
            ids = [x["offset_bytes"] for x in r]
            if len(set(ids)) != expected or any(off in seen for off in ids):
                raise ValueError("Repeated raw LBA target")
            seen.update(ids)
            samples = [float(x["read_ms"]) for x in r]
            if any(not math.isfinite(v) or v <= 0 for v in samples):
                raise ValueError("Nonpositive or invalid latency")
            total_ms = durations_ms[key]
            if not math.isfinite(total_ms) or total_ms <= 0:
                raise ValueError("Invalid profile duration")
            report.append({
                "round": trial, "mode": mode, "reads": expected,
                "bytes": expected * BLOCK,
                "elapsed_ms": round(total_ms, 4),
                "observed_MB_s": round(expected * BLOCK / (total_ms / 1000) / 1_000_000, 4),
                "p50_read_ms": round(statistics.median(samples), 4),
                "p95_read_ms": round(percentile(samples, 0.95), 4),
                "p99_read_ms": round(percentile(samples, 0.99), 4),
                "under_1ms_reads": sum(v < 1 for v in samples),
                "sum_absolute_lba_distance_bytes": sum(
                    int(x["distance_from_previous_bytes"] or 0) for x in r),
            })
    for trial in range(1, ROUNDS + 1):
        baseline = next(x["elapsed_ms"] for x in report
                        if x["round"] == trial and x["mode"] == "sequential")
        for x in report:
            if x["round"] == trial:
                x["elapsed_vs_sequential_percent"] = round(
                    (x["elapsed_ms"] / baseline - 1) * 100, 3)
    return report


def save_csv(path, rows):
    if not rows:
        raise ValueError("Cannot write empty CSV")
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def verify_output_location():
    """Refuse reparse-point results and any F: volume backed by target Disk 2."""
    if (os.name != "nt" or ROOT.drive.upper() != "F:"
            or ROOT.name.lower() != "zebra-ganta_ch2"):
        raise RuntimeError("Native Windows repository F:\\zebra-ganta_ch2 required")
    resolved = ROOT.resolve(strict=True)
    if resolved.drive.upper() != "F:" or resolved.name.lower() != "zebra-ganta_ch2":
        raise RuntimeError("Repository redirects outside F:")
    folder = ROOT / "results"
    if folder.is_symlink() or (hasattr(folder, "is_junction") and folder.is_junction()):
        raise RuntimeError("Results path is a reparse point")
    return folder


def verify_volumes():
    from lab import powershell_json
    info = powershell_json(
        "$t=Get-Partition -DriveLetter T -ErrorAction Stop;"
        "$v=Get-Volume -DriveLetter T -ErrorAction Stop;"
        "$f=Get-Partition -DriveLetter F -ErrorAction Stop;"
        "ConvertTo-Json -InputObject ([PSCustomObject]@{"
        "Tdisk=[int]$t.DiskNumber;Fdisk=[int]$f.DiskNumber;"
        "Tletter=[string]$t.DriveLetter;"
        "Tfs=[string]$v.FileSystem;Thealth=[string]$v.HealthStatus"
        "}) -Compress")
    if (not isinstance(info, dict) or info.get("Tdisk") != 2
            or info.get("Fdisk") == 2 or info.get("Tletter", "").upper() != "T"
            or info.get("Tfs", "").upper() != "NTFS"
            or info.get("Thealth", "").upper() != "HEALTHY"):
        raise RuntimeError("T: NTFS or F: output isolation failed")
    return info


def run_live(args, jobs):
    validate_args(args)
    out_parent = verify_output_location()
    from experiment004 import verify
    from experiment005 import check_usb_parent
    from transitions import single_read
    disk = verify(args)
    chain = check_usb_parent(args)
    volume_info = verify_volumes()
    print("HARDWARE:", json.dumps(disk, ensure_ascii=False))
    print("VOLUMES:", json.dumps(volume_info, ensure_ascii=False))
    print("TARGET: \\\\.\\PhysicalDrive2 (READ-ONLY); output: F:\\zebra-ganta_ch2\\results")
    print("No repeated LBA; cache/read-ahead still possible; NOT physical seek time.")
    confirmation = "READ HGST DISK 2 EXP008"
    if input("Type " + repr(confirmation) + " to proceed: ").strip() != confirmation:
        raise RuntimeError("Cancelled before raw disk access")
    if (verify(args) != disk or check_usb_parent(args) != chain
            or verify_volumes() != volume_info):
        raise RuntimeError("Device identity changed before read")
    out_parent = verify_output_location()
    out = out_parent / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                        + "-exp008-lba-traversal")
    out.mkdir(parents=True, exist_ok=False)
    fingerprint = hashlib.sha256(json.dumps(
        jobs, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    manifest = {
        "schema": "zebra-ganta.exp008.v1", "status": "incomplete",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "parent_experiment": "003", "disk": disk, "pnp_ancestors": chain,
        "volumes": volume_info, "bridge": args.bridge, "seed": args.seed,
        "blocks_per_zone": args.blocks_per_zone, "zones": ZONES,
        "rounds": ROUNDS, "modes": MODES, "read_bytes": BLOCK,
        "planned_reads": len(jobs), "planned_read_bytes": len(jobs) * BLOCK,
        "plan_sha256": fingerprint,
        "methods": ["read-only raw 4 KiB blocks", "distinct LBA per read",
                    "matched regional offsets, not identical addresses",
                    "three rotated mode-order rounds"],
        "limitations": [
            "Observed Windows + USB latency includes caching, read-ahead and scheduling",
            "Not physical head position, track distance or isolated seek time",
            "Different mode LBA addresses are similar in region but not identical",
            "Profile duration includes Python and IO stack overhead",
            "No data layout modification; not an Adaptive Macro Interleave test",
        ],
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    observed, durations = [], {}
    try:
        with open(r"\\.\PhysicalDrive2", "rb", buffering=0) as handle:
            for rnd in range(1, ROUNDS + 1):
                for slot in range(1, len(MODES) + 1):
                    trial = [x for x in jobs if x["round"] == rnd and x["slot"] == slot]
                    mode = trial[0]["mode"]
                    start = time.perf_counter_ns()
                    for job in trial:
                        ms = single_read(handle, job["offset_bytes"])
                        if not math.isfinite(ms) or ms <= 0:
                            raise ValueError("Invalid measured latency")
                        observed.append({**job, "read_ms": round(ms, 5)})
                    durations[(rnd, mode)] = (time.perf_counter_ns() - start) / 1_000_000
                    print("completed", rnd, mode, len(trial), "unique 4KiB reads")
    except (OSError, PermissionError, ValueError) as exc:
        if observed:
            save_csv(out / "observations_partial.csv", observed)
        (out / "error.txt").write_text(str(exc), encoding="utf-8")
        print("PARTIAL/FAILED; no retries or permission bypass", file=sys.stderr)
        return 2
    summary = summarize(observed, durations, args.blocks_per_zone)
    save_csv(out / "observations.csv", observed)
    save_csv(out / "summary.csv", summary)
    manifest["status"] = "complete"
    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUCCESS. Real observations are saved only on F:", out)
    print("Interpret as USB/Windows I/O behavior, NOT as measured head travel.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true",
                        help="Perform confirmed read-only physical HDD reads; default PLAN ONLY")
    parser.add_argument("--disk", type=int, default=2)
    parser.add_argument("--letter", default="T")
    parser.add_argument("--size", type=int, default=SIZE)
    parser.add_argument("--win32-size", type=int, default=WIN32_SIZE)
    parser.add_argument("--bridge", default="usb3-orico")
    parser.add_argument("--link-speed", default="Super")
    parser.add_argument("--vidpid", default="2109:0715")
    parser.add_argument("--blocks-per-zone", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20261113)
    args = parser.parse_args()
    try:
        validate_args(args)
        jobs = build_plan(args.blocks_per_zone, args.seed)
        if not args.run:
            print("PLAN ONLY — no disk inventory, raw reads or files created.")
            print(json.dumps({
                "experiment": "008", "extends": "003",
                "modes": MODES, "rounds": ROUNDS, "zones": ZONES,
                "blocks_per_zone": args.blocks_per_zone, "reads": len(jobs),
                "read_bytes": BLOCK, "total_read_bytes": len(jobs) * BLOCK,
                "unique_target_offsets": len({x["offset_bytes"] for x in jobs}),
                "round_mode_order": [
                    list(MODES[r:] + MODES[:r]) for r in range(ROUNDS)],
                "first_six_jobs": jobs[:6],
            }, ensure_ascii=False, indent=2))
            return 0
        return run_live(args, jobs)
    except (RuntimeError, ValueError, OSError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
