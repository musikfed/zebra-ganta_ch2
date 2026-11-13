#!/usr/bin/env python3
"""Experiment 007: optional NTFS file-extent inspection; METADATA ONLY.

Default: prints the intended checks and does not query a file.
With --run: uses Windows fsutil file queryextents on one explicitly selected
existing regular file on the documented HGST T: volume. No file contents,
raw disk reads, writes, moves, defragmentation or power/servo commands.
Output is console-only; never uploads filenames or file metadata.
The API reports NTFS logical extents, NOT physical magnetic tracks.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

# Support direct execution: uv run python tools/inspect_extents007.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiment004 import verify
from experiment005 import check_usb_parent
from lab import DEFAULT_SIZE, powershell_json
from tools.parse_extents007 import parse_extents

SAFE_TARGET = dict(disk=2,letter="T",size=DEFAULT_SIZE,
                   win32_size=500105249280,bridge="usb3-orico",
                   link_speed="Super",vidpid="2109:0715")


def validate_selected(path: str) -> Path:
    """Pure lexical safety rules; does not inspect device or file contents."""
    if not path or not isinstance(path,str):
        raise ValueError("An explicit file path is required")
    if not path.upper().startswith("T:\\"):
        raise ValueError("Expected an absolute path on T: only")
    if "\x00" in path or '"' in path or "\n" in path or "\r" in path:
        raise ValueError("Unsafe file-path characters")
    # Prevent ambiguous relative traversal and device-name notation.
    raw_parts=path.replace("/","\\").split("\\")
    if any(part in ("",".","..") for part in raw_parts[1:]):
        raise ValueError("Path must be canonical; no empty/dot/dotdot parts")
    return Path(path)


def run(file_path: Path) -> int:
    if os.name!="nt":
        raise RuntimeError("This inspection requires native Windows")
    if Path(__file__).resolve().parent.parent.drive.upper()!="F:":
        raise RuntimeError("Use repository on F:; this tool never stores outputs")
    if not file_path.is_file() or file_path.is_symlink():
        raise RuntimeError("Chosen file does not exist as an ordinary file")
    actual=file_path.resolve(strict=True)
    if actual.drive.upper()!="T:":
        raise RuntimeError("Resolved file is not on T:; refusing reparse/symlink target")
    args=SimpleNamespace(**SAFE_TARGET)
    original=verify(args)
    chain=check_usb_parent(args)
    fs = powershell_json("$v=Get-Volume -DriveLetter T -ErrorAction Stop;"
                         "ConvertTo-Json -InputObject ([PSCustomObject]@{"
                         "DriveLetter=[string]$v.DriveLetter;"
                         "FileSystem=[string]$v.FileSystem;"
                         "HealthStatus=[string]$v.HealthStatus}) -Compress")
    if not isinstance(fs,dict) or str(fs.get("FileSystem","")).upper()!="NTFS":
        raise RuntimeError("Expected NTFS; no extent command issued")
    print("READ-ONLY METADATA INSPECTION: T: HGST Disk 2 / NTFS verified.")
    print("Selected filename is local; do not publish if private:",actual.name)
    print("Windows NTFS VCN/LCN mapping, NOT physical head or magnetic geometry.")
    if verify(args)!=original or check_usb_parent(args)!=chain:
        raise RuntimeError("Hardware identity changed")
    cmd=["fsutil.exe","file","queryextents",str(actual)]
    result=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          timeout=30,check=False)
    err=result.stderr.decode("utf-8-sig","replace")
    if result.returncode!=0:
        raise RuntimeError("fsutil queryextents unsupported/denied (no bypass): "+err[:400])
    mapped=parse_extents(result.stdout)
    print("===== NTFS LOGICAL EXTENTS (structured JSON) =====")
    print(json.dumps(mapped,ensure_ascii=False,indent=2))
    print("Interpretation: file allocation only. True magnetic boundaries UNKNOWN.")
    return 0



def run_volume() -> int:
    """Identify the exact HGST T: and display OS-reported filesystem metadata.

    No file needed, no raw sector reads and no writes. fsutil fsinfo ntfsinfo
    obtains filesystem structure, not the physical allocation of a user file.
    """
    if os.name != "nt":
        raise RuntimeError("Volume inventory requires native Windows")
    if Path(__file__).resolve().parent.parent.drive.upper() != "F:":
        raise RuntimeError("Repository must be on F:")
    args=SimpleNamespace(**SAFE_TARGET)
    before=verify(args)
    ancestors=check_usb_parent(args)
    info=powershell_json(
        "$p=Get-Partition -DriveLetter T -ErrorAction Stop;"
        "$v=Get-Volume -DriveLetter T -ErrorAction Stop;"
        "if($p.DiskNumber -ne 2 -or $v.FileSystem -ne 'NTFS' -or "
        "$v.HealthStatus -ne 'Healthy'){throw 'T volume mismatch'};"
        "ConvertTo-Json -InputObject ([PSCustomObject]@{"
        "DiskNumber=[int]$p.DiskNumber;"
        "DriveLetter=[string]$p.DriveLetter;"
        "FileSystem=[string]$v.FileSystem;"
        "HealthStatus=[string]$v.HealthStatus;"
        "SizeBytes=[int64]$v.Size;"
        "FreeBytes=[int64]$v.SizeRemaining}) -Compress"
    )
    if not isinstance(info,dict) or info.get("DiskNumber") != 2 or (
            info.get("DriveLetter","").upper()!="T" or info.get("FileSystem")!="NTFS"
            or info.get("HealthStatus")!="Healthy"):
        raise RuntimeError("HGST T: volume verification failed")
    if verify(args)!=before or check_usb_parent(args)!=ancestors:
        raise RuntimeError("HGST identity changed during inspection")
    print("READ-ONLY VERIFIED HGST Disk 2 / T: / NTFS — filesystem metadata only")
    print(json.dumps(info,ensure_ascii=False,indent=2))
    # This exact subcommand queries filesystem metadata. It does not create
    # files or expose physical magnetic sector / actuator locations.
    cp=subprocess.run(["fsutil.exe","fsinfo","ntfsinfo","T:"],
                      capture_output=True,timeout=30,check=False)
    if cp.returncode:
        raise RuntimeError("fsutil fsinfo ntfsinfo failed; no fallback performed")
    print("===== NTFS VOLUME METADATA (console code page may vary) =====")
    print(cp.stdout.decode("cp866","replace"))
    print("This cannot map the extents of nonexistent user files.")
    return 0

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file",help="Existing single ordinary file on HGST T:")
    p.add_argument("--volume",action="store_true",help="Inspect verified T: NTFS volume metadata, without requiring a file")
    p.add_argument("--run",action="store_true",
                   help="Run metadata-only FSUTIL query, after hardware verification")
    a=p.parse_args()
    try:
        if a.volume == bool(a.file):
            raise ValueError("Provide exactly one of --volume or --file")
        if a.volume:
            if not a.run:
                print("PLAN ONLY: T: HGST Disk 2 / VIA USB / NTFS volume metadata; zero device I/O")
                return 0
            return run_volume()
        selected=validate_selected(a.file)
        if not a.run:
            print("PLAN ONLY: will verify HGST Disk 2, T:, USB VID/PID and NTFS; "
                  "then query file-extents metadata only.")
            print("No filesystem/device commands issued. No files created.")
            return 0
        return run(selected)
    except (ValueError,RuntimeError,OSError,subprocess.TimeoutExpired) as exc:
        print("ERROR:",exc,file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
