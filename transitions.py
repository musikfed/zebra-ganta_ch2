#!/usr/bin/env python3
"""Exp 003: observed latency of bounded raw reads at near/far LBA transitions.

This is NOT a mechanical seek-time measurement. Windows, USB, buffering,
rotation and command scheduling are confounders. No write commands exist.
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

from lab import DEFAULT_SIZE, EXPECTED_TARGET, MIB, identify, inventory

BLOCK = 4096
MIN_GAP = 2 * MIB
MAX_PAIRS = 200


def plan(size: int, pairs: int, seed: int):
    """Pairs with comparable start regions, alternating near and far jumps."""
    if not 4 <= pairs <= MAX_PAIRS:
        raise ValueError("pairs must be 4..200")
    rng = random.Random(seed)
    result = []
    # 15-35% home zones; 65-85% far zones. Each pair has unique offsets.
    # Comparing modes still has order and radial-position confounding.
    for i in range(pairs):
        home = int(size * (0.15 + 0.20 * (i + 0.5) / pairs)) // BLOCK * BLOCK
        far = int(size * (0.65 + 0.20 * (i + 0.5) / pairs)) // BLOCK * BLOCK
        home += (i % 17) * 8 * MIB
        far += (i % 17) * 8 * MIB
        home = (home // BLOCK) * BLOCK
        far = (far // BLOCK) * BLOCK
        if not (0 < home < size-BLOCK and 0 < far < size-BLOCK):
            raise ValueError("planned sample outside device")
        near = home + MIN_GAP
        assert near + BLOCK < size
        result.append((home, near, far))
    rng.shuffle(result)
    return result


def single_read(handle, offset: int) -> float:
    handle.seek(offset, os.SEEK_SET)
    start = time.perf_counter_ns()
    payload = handle.read(BLOCK)
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
    if len(payload) != BLOCK:
        raise OSError(f"Short read at {offset}: {len(payload)} of {BLOCK}")
    return elapsed_ms


def run(args) -> int:
    if os.name != "nt":
        raise RuntimeError("Live test requires native Windows (not WSL).")
    if args.disk != 2 or args.expect_model.upper() != EXPECTED_TARGET:
        raise RuntimeError("Protocol locked to verified HGST Disk 2.")
    if args.expect_size != DEFAULT_SIZE:
        raise RuntimeError("Protocol locked to Get-Disk size for this HGST.")
    disk = identify(inventory(), args.disk, args.expect_model, args.expect_size)
    if Path.cwd().drive.upper() != "F:":
        raise RuntimeError("Run within F: project so result files cannot be written to T:.")
    print("TARGET VERIFIED:", json.dumps(disk, ensure_ascii=False))
    print("Read-only 4 KiB operations. Timing includes USB and Windows overhead.")
    print("This is NOT a calibrated physical head-positioning test.")
    if input("Type READ HGST DISK 2: ").strip() != "READ HGST DISK 2":
        raise RuntimeError("Cancelled; no disk reads.")
    if identify(inventory(), args.disk, args.expect_model, args.expect_size) != disk:
        raise RuntimeError("Device inventory changed before test.")
    jobs = plan(args.expect_size, args.pairs, args.seed)
    out = Path.cwd() / "results" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-transitions")
    out.mkdir(parents=True, exist_ok=False)
    records = []
    try:
        with open(r"\\.\PhysicalDrive2", "rb", buffering=0) as f:
            # Equalize order by alternating near/far first.
            # The anchor read is included in the protocol, not in target latency.
            for i, (home, near, far) in enumerate(jobs):
                modes = [("near", near), ("far", far)] if i % 2 == 0 else [("far", far), ("near", near)]
                for mode, target in modes:
                    anchor_ms = single_read(f, home)
                    elapsed = single_read(f, target)
                    records.append({
                        "pair": i+1, "mode": mode, "anchor_offset": home,
                        "target_offset": target, "distance_bytes": abs(target-home),
                        "anchor_ms": round(anchor_ms, 5),
                        "target_read_ms": round(elapsed, 5),
                        "bytes": BLOCK
                    })
                if (i+1) % 8 == 0:
                    print(f"paired comparisons: {i+1}/{len(jobs)}")
    except OSError as exc:
        (out/"error.txt").write_text(str(exc), encoding="utf-8")
        raise
    with (out/"observations.csv").open("w", encoding="utf-8-sig", newline="") as file:
        w = csv.DictWriter(file, fieldnames=list(records[0]))
        w.writeheader(); w.writerows(records)
    med = {mode: statistics.median(r["target_read_ms"] for r in records if r["mode"] == mode)
           for mode in ("near","far")}
    delta = med["far"] - med["near"]
    manifest = {
        "experiment": "003: near-vs-far 4KiB raw read after anchor",
        "type": "real observed timings, NOT physical seek time",
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "disk": disk, "pairs": args.pairs, "seed": args.seed,
        "sample_block_bytes": BLOCK, "near_gap_bytes": MIN_GAP,
        "median_target_read_ms": med, "observed_delta_ms": delta,
        "limitations": ["No OS or USB cache control", "USB link speed unknown",
            "Modes involve different radial ranges", "Windows read scheduling and rotation affect timing",
            "No proof that target time differences equal head seek costs"]
    }
    (out/"manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Near median:", round(med["near"], 4), "ms; far:", round(med["far"],4),
          "ms; observed delta:", round(delta,4), "ms")
    print("Interpretation: preliminary near/far read latency, not calibrated seek.")
    print("Saved:",out)
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--disk",type=int,required=True)
    p.add_argument("--expect-model",required=True)
    p.add_argument("--expect-size",type=int,required=True)
    p.add_argument("--pairs",type=int,default=40)
    p.add_argument("--seed",type=int,default=20261112)
    args=p.parse_args()
    try:
        return run(args)
    except (RuntimeError, ValueError, OSError) as e:
        print("ERROR:",e,file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
