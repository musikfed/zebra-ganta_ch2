#!/usr/bin/env python3
"""Analyze actual chapter 3 CSV files; never generates or invents measurements."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics
import sys


def summarize(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        rows = list(csv.DictReader(fp))
    pairs = {}
    for row in rows:
        pair = int(row["pair"])
        mode = row["mode"]
        if mode not in ("near", "far"):
            raise ValueError(f"Unexpected mode {mode!r} in {path}")
        ms = float(row["target_read_ms"])
        if ms < 0 or pair < 1 or mode in pairs.setdefault(pair, {}):
            raise ValueError(f"Invalid / repeated row for pair {pair}, mode {mode}")
        pairs[pair][mode] = ms
    if not pairs or any(set(v) != {"near", "far"} for v in pairs.values()):
        raise ValueError(f"Incomplete near/far pairs in {path}")
    ordered = [pairs[i] for i in sorted(pairs)]
    near = [r["near"] for r in ordered]
    far = [r["far"] for r in ordered]
    differences = [r["far"]-r["near"] for r in ordered]
    return {
        "source": str(path),
        "pairs": len(ordered),
        "near_median_ms": statistics.median(near),
        "far_median_ms": statistics.median(far),
        "difference_of_medians_ms": statistics.median(far)-statistics.median(near),
        "median_of_paired_differences_ms": statistics.median(differences),
        "paired_positive_count": sum(d>0 for d in differences),
        "paired_zero_count": sum(d==0 for d in differences),
        "paired_negative_count": sum(d<0 for d in differences),
        "near_min_max_ms": [min(near),max(near)],
        "far_min_max_ms": [min(far),max(far)],
        "paired_difference_min_max_ms": [min(differences),max(differences)],
        "warning": "Observed Windows+USB read latency, NOT isolated head seek time",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", nargs="+", type=Path, help="One or more original observations.csv files")
    a = p.parse_args()
    try:
        results = [summarize(path) for path in a.csv]
    except (OSError, ValueError, KeyError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("No physical seek-time inference or speedup claims.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
