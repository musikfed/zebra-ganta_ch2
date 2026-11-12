#!/usr/bin/env python3
"""PEGINELAB HDD Lab 001 — bounded, read-only physical-disk sampling for Windows.

Python 3.12+. Standard library only. No destructive operations are implemented.
The device is read through the Windows file interface, which can contain caching
effects. Do not interpret measured latency as pure head-seek time.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
import re
from pathlib import Path
import statistics
import subprocess
import sys
import time

EXPECTED_TARGET = "HTS725050B7E630"
DEFAULT_SIZE = 500_106_780_160
WIN32_REPORTED_SIZE = 500_105_249_280
MIB = 1024 * 1024
ALIGNMENT = 4096
SCHEMA = "peginelab.hddlab.001.v1"


def powershell_json(code: str):
    command = [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
        "Bypass", "-Command",
        "$ErrorActionPreference='Stop'; " + code
    ]
    result = subprocess.run(command, capture_output=True, check=False, timeout=25)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError("PowerShell hardware inventory failed: " + err[:1000])
    raw = result.stdout.decode("utf-8-sig", errors="replace").strip()
    if not raw:
        raise RuntimeError("PowerShell returned no disk inventory.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Cannot parse PowerShell disk inventory: " + raw[:500]) from exc


def inventory():
    # ConvertTo-Json can output a single object or an array; normalize below.
    code = (
        "$items = @(Get-Disk | ForEach-Object { "
        "$d = $_; "
        "$w = Get-CimInstance Win32_DiskDrive | Where-Object { $_.Index -eq $d.Number } | Select-Object -First 1; "
        "[PSCustomObject]@{ Number=[int]$d.Number; FriendlyName=[string]$d.FriendlyName; "
        "Model=[string]$w.Model; Size=[int64]$d.Size; "
        "Win32Size=[int64]$w.Size; "
        "BusType=[string]$d.BusType; IsBoot=[bool]$d.IsBoot; "
        "IsSystem=[bool]$d.IsSystem; IsOffline=[bool]$d.IsOffline; "
        "OperationalStatus=[string]$d.OperationalStatus } "
        "}); ConvertTo-Json -InputObject $items -Depth 3 -Compress"
    )
    obj = powershell_json(code)
    return obj if isinstance(obj, list) else [obj]


def normalize_model(value: str) -> str:
    """Allow vendor-inserted spaces but not missing/replaced model characters."""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def identify(items, number: int, model_fragment: str, expected_size: int):
    matches = [d for d in items if int(d["Number"]) == number]
    if len(matches) != 1:
        raise RuntimeError("Disk number missing or ambiguous. No read attempted.")
    disk = matches[0]
    model = (disk.get("Model") or "") + " " + (disk.get("FriendlyName") or "")
    if normalize_model(model_fragment) not in normalize_model(model):
        raise RuntimeError("Disk model mismatch. No read attempted: " + model)
    if int(disk.get("Size", 0)) != expected_size:
        raise RuntimeError("Disk size mismatch. No read attempted.")
    # Cross-check both Windows inventory APIs; USB bridges may report
    # slightly different geometry. Record that discrepancy, never ignore it.
    if int(disk.get("Win32Size", 0)) != WIN32_REPORTED_SIZE:
        raise RuntimeError("Win32 disk capacity differs from documented value. No read attempted.")
    if disk.get("IsBoot") or disk.get("IsSystem"):
        raise RuntimeError("Refusing system or boot disk.")
    if disk.get("IsOffline"):
        raise RuntimeError("Refusing offline disk.")
    if "USB" not in disk.get("BusType", "").upper():
        raise RuntimeError("This protocol requires the documented USB test connection.")
    if disk.get("OperationalStatus", "").lower() != "online":
        raise RuntimeError("Disk is not online.")
    return disk


def offsets(size: int, samples: int, length: int):
    """Spread bounded aligned reads over 5%-95% physical address space."""
    if samples < 3 or samples > 21:
        raise ValueError("samples must be in range 3..21")
    if length % ALIGNMENT:
        raise ValueError("read length must be aligned to 4096 bytes")
    out = []
    for i in range(samples):
        fraction = 0.05 + 0.90 * i / (samples - 1)
        off = int((size - length) * fraction) // ALIGNMENT * ALIGNMENT
        if off < ALIGNMENT or off + length > size - ALIGNMENT:
            raise ValueError("unsafe sampling range")
        out.append((round(fraction * 100, 2), off))
    if len({x[1] for x in out}) != samples:
        raise ValueError("sampling offsets are not unique")
    return out


def read_exact(handle, offset: int, length: int) -> float:
    handle.seek(offset, os.SEEK_SET)
    start = time.perf_counter_ns()
    remaining = length
    while remaining:
        data = handle.read(min(remaining, 4 * MIB))
        if not data:
            raise OSError("Short physical-device read (EOF)")
        remaining -= len(data)
    elapsed_s = (time.perf_counter_ns() - start) / 1e9
    if elapsed_s <= 0:
        raise RuntimeError("Invalid clock measurement")
    return elapsed_s


def write_svg(summary: list[dict], target: Path):
    width, height = 900, 460
    left, right, top, bottom = 85, 30, 40, 70
    plot_w = width - left - right
    plot_h = height - top - bottom
    ceiling = max((r["median_MB_s"] for r in summary), default=1)
    ceiling = max(10.0, math.ceil(ceiling / 10) * 10)
    def xy(row):
        return (
            left + (float(row["position_percent"]) / 100) * plot_w,
            top + plot_h * (1 - float(row["median_MB_s"]) / ceiling),
        )
    lines = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 460">',
             '<rect width="900" height="460" fill="white"/>',
             '<text x="450" y="24" font-size="19" text-anchor="middle" fill="#222">PEGINELAB — observed HDD read throughput</text>']
    for n in range(6):
        y = top + plot_h * n / 5
        value = ceiling * (1 - n / 5)
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#dedede"/>')
        lines.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" font-size="12">{value:.0f}</text>')
    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#222"/>')
    lines.append(f'<line x1="{left}" y1="{top+plot_h}" x2="{width-right}" y2="{top+plot_h}" stroke="#222"/>')
    for n in range(0, 101, 20):
        x = left + n/100*plot_w
        lines.append(f'<text x="{x:.1f}" y="{height-48}" text-anchor="middle" font-size="12">{n}%</text>')
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in map(xy, summary))
    lines.append(f'<polyline points="{pts}" fill="none" stroke="#ba6d22" stroke-width="3"/>')
    for x, y in map(xy, summary):
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#ba6d22"/>')
    lines.append('<text x="450" y="438" font-size="14" text-anchor="middle">Sample location in physical LBA space (%)</text>')
    lines.append('<text x="17" y="230" transform="rotate(-90 17 230)" font-size="14" text-anchor="middle">MB/s (decimal, 10^6)</text>')
    lines.append('<text x="450" y="55" font-size="11" text-anchor="middle" fill="#555">USB/Windows path; caching not ruled out; no proof of physical track geometry</text>')
    lines.append('</svg>')
    target.write_text("\n".join(lines), encoding="utf-8")


def run_scan(args):
    if os.name != "nt":
        raise RuntimeError("Live scan is Windows-only.")
    if args.disk != 2:
        raise RuntimeError("This first protocol is LOCKED to disk number 2.")
    if args.expect_model.upper() != EXPECTED_TARGET:
        raise RuntimeError("This first protocol is LOCKED to the documented HGST model.")
    if args.expect_size != DEFAULT_SIZE:
        raise RuntimeError("This first protocol is LOCKED to the documented exact capacity.")
    if not 1 <= args.mib <= 32 or args.mib & (args.mib - 1):
        raise RuntimeError("--mib must be 1, 2, 4, 8, 16 or 32.")
    if not 1 <= args.repeats <= 5:
        raise RuntimeError("--repeats must be 1..5.")
    if not 3 <= args.samples <= 21:
        raise RuntimeError("--samples must be 3..21.")
    items = inventory()
    disk = identify(items, args.disk, args.expect_model, args.expect_size)
    print("\nVERIFIED TARGET (read-only):")
    for key in ("Number", "Model", "FriendlyName", "Size", "Win32Size", "BusType",
                "IsSystem", "IsBoot", "OperationalStatus"):
        print(f"  {key}: {disk.get(key)}")
    print("\nWARNING: raw device access may fail under USB/Windows.")
    print("No formatting, writing, mount changes or security bypass will be attempted.")
    print("USB/Windows cache may distort measurements. Do not call this pure HDD speed.")
    expected = "READ HGST DISK 2"
    confirm = input(f"\nType '{expected}' to proceed: ").strip()
    if confirm != expected:
        raise RuntimeError("Not confirmed. Nothing read.")
    # Guard against device renumbering or hot-swap between confirmation and open.
    fresh = identify(inventory(), args.disk, args.expect_model, args.expect_size)
    if fresh != disk:
        raise RuntimeError("Disk inventory changed since confirmation. No read attempted.")
    length = args.mib * MIB
    zones = offsets(args.expect_size, args.samples, length)
    # Results path is local working directory, not USB drive.
    out_root = Path.cwd().resolve() / "results"
    if os.path.splitdrive(str(out_root))[0].upper() == "T:":
        raise RuntimeError("Do not run from T:. Results must stay off the test HDD.")
    target_dir = out_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema": SCHEMA,
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "001: bounded read of several LBA ranges",
        "disk": disk,
        "device_path": r"\\.\PhysicalDrive2",
        "os": sys.platform, "python": sys.version.split()[0],
        "sample_count": args.samples, "repeats": args.repeats, "read_mib": args.mib,
        "methods": ["os.O_RDONLY", "os.SEEK_SET", "perf_counter_ns", "buffered Windows raw I/O"],
        "limitations": [
            "USB bridge/JMicron and Windows storage cache can alter results",
            "no direct measurement of physical head seek",
            "full ATA SMART inaccessible via current USB bridge",
            "raw physical LBA ranges are not a verified map of tracks",
        ],
    }
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    records = []
    path = r"\\.\PhysicalDrive2"
    print(f"\nAttempting read-only device open: {path}")
    try:
        with open(path, "rb", buffering=0) as handle:
            # Reverse order every second repeat to expose order / cache effects.
            for repeat in range(1, args.repeats + 1):
                sequence = zones if repeat % 2 else list(reversed(zones))
                for percent, offset in sequence:
                    elapsed = read_exact(handle, offset, length)
                    speed = length / elapsed / 1_000_000
                    row = {
                        "repeat": repeat, "position_percent": percent,
                        "offset_bytes": offset, "read_bytes": length,
                        "seconds": round(elapsed, 7),
                        "MB_s": round(speed, 3),
                    }
                    records.append(row)
                    print(f"repeat={repeat} zone={percent:5.1f}% "
                          f"speed={speed:8.2f} MB/s latency={elapsed:.3f} s")
    except (PermissionError, OSError) as exc:
        (target_dir / "error.txt").write_text(str(exc), encoding="utf-8")
        print(f"Read blocked or failed: {exc}\nSaved diagnostics: {target_dir}")
        return 2

    with (target_dir / "measurements.csv").open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    summary = []
    for percent, _ in zones:
        speeds = [r["MB_s"] for r in records if r["position_percent"] == percent]
        summary.append({
            "position_percent": percent,
            "median_MB_s": round(statistics.median(speeds), 3),
            "min_MB_s": min(speeds), "max_MB_s": max(speeds),
            "repeat_count": len(speeds),
        })
    with (target_dir / "summary.csv").open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    write_svg(summary, target_dir / "speed.svg")
    print(f"\nSaved CSV, JSON and SVG to: {target_dir}")
    print("These are observed timings through Windows + USB, not a proven HDD acceleration.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inspect", help="Show disk inventory; no disk reads.")
    scan = sub.add_parser("scan", help="Guarded read-only sample of HGST Disk 2.")
    scan.add_argument("--disk", type=int, required=True)
    scan.add_argument("--expect-model", required=True)
    scan.add_argument("--expect-size", type=int, required=True)
    scan.add_argument("--samples", type=int, default=5)
    scan.add_argument("--mib", type=int, default=16)
    scan.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    try:
        if args.cmd == "inspect":
            print(json.dumps(inventory(), ensure_ascii=False, indent=2))
            return 0
        return run_scan(args)
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
