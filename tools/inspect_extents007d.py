#!/usr/bin/env python3
"""NTFS D: extent inspection on known Acer SATA SSD: metadata only.

Default PLAN ONLY: checks path syntax; NO filesystem queries, file reads/writes.
--run verifies Disk 0 AMD R5SL120G, exact serial, D: NTFS and an existing
ordinary file, then invokes Windows fsutil file queryextents.
Do not use this tool to map HGST T:; its separate read-only inspector remains.
No data is written, deleted, moved, formatted, uploaded or saved.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys

try:
    from tools.parse_extents007 import parse_extents
except ModuleNotFoundError:
    # Direct script execution inserts tools/ into sys.path, while unittest
    # imports tools.inspect_extents007d from the repository root.
    from parse_extents007 import parse_extents

EXPECTED_DISK = 0
EXPECTED_MODEL = "AMD R5SL120G"
EXPECTED_SERIAL = "12012221W1021"
EXPECTED_SIZE = 120034123776


def validate_path(raw: str) -> PureWindowsPath:
    if not isinstance(raw, str) or not raw or any(c in raw for c in ('"', "\x00", "\n", "\r", "|", "*", "?")):
        raise ValueError("Expected a safe absolute path to one existing D: file")
    if "/" in raw or not raw.upper().startswith("D:\\"):
        raise ValueError("Only absolute canonical D: paths accepted; no HGST T: or system drives")
    parts = raw[3:].split("\\")
    if not parts or any(x in ("", ".", "..") or x.endswith((" ", ".")) or ":" in x for x in parts):
        raise ValueError("Ambiguous path segment")
    return PureWindowsPath(raw)


def verified_d_volume() -> None:
    script = r"""
$ErrorActionPreference = 'Stop'
$p = Get-Partition -DriveLetter D -ErrorAction Stop
$d = Get-Disk -Number $p.DiskNumber -ErrorAction Stop
$v = Get-Volume -DriveLetter D -ErrorAction Stop
[PSCustomObject]@{
  DiskNumber = [int]$d.Number
  Model = [string]$d.FriendlyName
  Serial = [string]$d.SerialNumber
  BusType = [string]$d.BusType
  Size = [int64]$d.Size
  IsBoot = [bool]$d.IsBoot
  IsSystem = [bool]$d.IsSystem
  Letter = [string]$p.DriveLetter
  FileSystem = [string]$v.FileSystem
  Health = [string]$v.HealthStatus
} | ConvertTo-Json -Compress
"""
    cp = subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",script],
                        capture_output=True,timeout=30,check=False)
    if cp.returncode:
        raise RuntimeError("Cannot verify D: volume; refusing extent query")
    try:
        d=json.loads(cp.stdout.decode("utf-8-sig"))
    except (UnicodeError,json.JSONDecodeError) as exc:
        raise RuntimeError("Invalid D: identity response") from exc
    if not (d.get("DiskNumber")==EXPECTED_DISK
            and d.get("Model","").strip().upper()==EXPECTED_MODEL
            and d.get("Serial","").strip().upper()==EXPECTED_SERIAL
            and d.get("BusType","").upper()=="SATA"
            and d.get("Size")==EXPECTED_SIZE
            and d.get("IsBoot") is False
            and d.get("IsSystem") is False
            and d.get("Letter","").upper()=="D"
            and d.get("FileSystem","").upper()=="NTFS"
            and d.get("Health","").upper()=="HEALTHY"):
        raise RuntimeError("D: identity or health differs from approved inventory; stop")


def inspect(raw: str) -> int:
    validate_path(raw)
    if os.name != "nt":
        raise RuntimeError("Native Windows required")
    # Reject links and junctions in any traversed component; no reparse redirects.
    p=Path(raw)
    parent=p.anchor
    for part in p.parts[1:]:
        parent=os.path.join(parent,part)
        component=Path(parent)
        if component.is_symlink() or (hasattr(component,"is_junction") and component.is_junction()):
            raise RuntimeError("Reparse point/junction detected; refusing")
    if not p.is_file():
        raise RuntimeError("Selected D: file does not exist or is not an ordinary file")
    resolved=p.resolve(strict=True)
    if resolved.drive.upper()!="D:" or not resolved.is_file():
        raise RuntimeError("File resolves outside D: or no longer exists")
    verified_d_volume()
    # Query once more after file checks, before opening the file handle in fsutil.
    verified_d_volume()
    cp=subprocess.run(["fsutil.exe","file","queryextents",str(resolved)],
                      capture_output=True,timeout=30,check=False)
    if cp.returncode:
        raise RuntimeError("fsutil queryextents refused/unsupported (no permission bypass)")
    mapped = parse_extents(cp.stdout)
    print("NTFS logical VCN/LCN extents only — NOT magnetic tracks.")
    print(json.dumps(mapped, ensure_ascii=False, indent=2))
    print("NOTE: LCN=null indicates unallocated/sparse run; compression requires independent check.")
    print("No files created or changed by this tool; file path not stored.")
    return 0


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file",required=True)
    ap.add_argument("--run",action="store_true",help="Read existing file metadata only")
    args=ap.parse_args()
    try:
        validate_path(args.file)
        if not args.run:
            print("PLAN ONLY — zero file/device access. Will verify D: SATA SSD Disk 0 "
                  "model/serial/size, NTFS, and an existing file before metadata query.")
            print("No physical reads, writes, deletes or file creation.")
            return 0
        return inspect(args.file)
    except (ValueError,RuntimeError,OSError,subprocess.TimeoutExpired) as exc:
        print("ERROR:",exc,file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
