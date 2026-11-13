#!/usr/bin/env python3
r"""Transfer previously captured Acer laboratory CSV files to GitHub safely.

Default PLAN ONLY. --publish copies the EXACT CSV bytes into data/raw,
adds a sanitized provenance.json, commits ONLY those exact files and pushes
main via locally configured Git credentials. Does not touch or read T:/HDD.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "results"
TARGET_ROOT = ROOT / "data" / "raw"
DATASETS = (
    ("exp003-run1", "20261112T185114Z-transitions", "003", 40, None),
    ("exp003-run2", "20261112T185549Z-transitions", "003", 40, None),
    ("exp003-run3", "20261112T185935Z-transitions", "003", 80, None),
    ("exp008-ntfs-hgst", "20261113T120828Z-exp008-ntfs-hgst", "008", 512, 4),
    ("exp009-size-ntfs", "20261113T123121Z-exp009-size-ntfs", "009", 180, 15),
)
MAX_CSV_BYTES = 2_000_000
CSV_NAMES = {"observations.csv", "summary.csv"}

def git(*args: str) -> str:
    cp = subprocess.run(("git", *args), cwd=ROOT, check=False,
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace")
    if cp.returncode:
        raise RuntimeError(f"git {args[0]} failed: {cp.stderr.strip() or cp.stdout.strip()}")
    return cp.stdout.strip()

def csv_info(blob: bytes):
    if not 0 < len(blob) <= MAX_CSV_BYTES:
        raise ValueError("Missing, empty or oversized original CSV")
    try:
        text=blob.decode("utf-8-sig")
        rows=list(csv.DictReader(text.splitlines()))
    except (UnicodeError, csv.Error) as e:
        raise ValueError("Invalid CSV encoding/content") from e
    if not rows or not all(rows[0]) or any(None in r for r in rows):
        raise ValueError("Invalid CSV header or inconsistent columns")
    return rows, set(rows[0])

def read_source(folder: Path, name: str):
    if name not in CSV_NAMES:raise ValueError("Unexpected CSV path")
    file=folder/name
    if file.is_symlink() or not file.is_file():
        raise ValueError(f"Missing/symlink input: {file}")
    if file.resolve().parent != folder.resolve():
        raise ValueError("Source not inside expected results directory")
    data=file.read_bytes()
    rows,fields=csv_info(data)
    return data,rows,fields

def public_manifest(original, exp, folder, files):
    """Allowlist only public, non-identifying metadata. Never copy PnP ancestry."""
    out = {
       "dataset": folder,
       "experiment": exp,
       "provenance": "original CSV bytes copied from Acer F: after real read-only HGST lab run",
       "source_drive_volume": "physical HGST Disk 2, T: NTFS, read only",
       "source_original_manifest_sha256": original["_digest"],
       "files": files,
       "limitations": "Windows/USB timing is not pure physical seek; no Zebra layout speedup proved",
    }
    safe_keys = {
       "003": ("date_utc", "pairs", "seed", "sample_block_bytes", "near_gap_bytes"),
       "008": ("time_utc", "seed", "count_per_trace", "traces", "block_bytes", "format"),
       "009": ("timestamp_utc", "seed", "per_zone", "zones", "sizes_kib", "read_only", "sample_count"),
    }
    for field in safe_keys[exp]:
        if field in original and isinstance(original[field], (str, int, float, bool, list)):
            out[field]=original[field]
    return out

def discover():
    prepared=[]
    for label,folder_name,exp,expected_obs,expected_summary in DATASETS:
        src=SRC_ROOT/folder_name
        if src.is_symlink() or not src.is_dir() or src.resolve().parent != SRC_ROOT.resolve():
            raise ValueError(f"Source directory missing or unexpected: {src}")
        manifest_file=src/"manifest.json"
        if manifest_file.is_symlink() or not manifest_file.is_file():
            raise ValueError("Missing original manifest: "+str(manifest_file))
        manifest_bytes=manifest_file.read_bytes()
        if len(manifest_bytes)>100_000:raise ValueError("Oversized manifest")
        raw=json.loads(manifest_bytes.decode("utf-8-sig"))
        if not isinstance(raw,dict):raise ValueError("Unexpected manifest structure")
        if exp in ("008","009"):
            if raw.get("schema")!=f"zebra-ganta.exp{exp}.v1" or raw.get("status")!="complete":
                raise ValueError(f"Manifest not complete: {folder_name}")
        else:
            if int(raw.get("pairs",-1))*2!=expected_obs:
                raise ValueError("Unexpected near/far manifest pairs")
        names=("observations.csv","summary.csv") if expected_summary else ("observations.csv",)
        payloads={}
        info={}
        for name in names:
            blob,rows,fields=read_source(src,name)
            target_count=expected_obs if name=="observations.csv" else expected_summary
            if len(rows)!=target_count:
                raise ValueError(f"{folder_name}/{name}: expected {target_count} rows, got {len(rows)}")
            required={"003":{"pair","mode","anchor_offset","target_offset","target_read_ms"},
                "008":{"trace","mode","sequence","offset_bytes","target_read_ms"},
                "009":{"zone_percent","size_kib","offset_bytes","read_bytes","read_ms","MB_s"}}
            if name=="observations.csv" and not required[exp].issubset(fields):
                raise ValueError(f"{folder_name}: CSV required fields missing")
            payloads[name]=blob
            info[name]={"sha256":hashlib.sha256(blob).hexdigest(),"rows":len(rows),"bytes":len(blob)}
        raw["_digest"]=hashlib.sha256(manifest_bytes).hexdigest()
        public=public_manifest(raw,exp,folder_name,info)
        prepared.append((label, payloads, (json.dumps(public,ensure_ascii=False,indent=2)+"\n").encode("utf-8"),info))
    return prepared

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--publish",action="store_true",help="Write only data/raw, git add/commit/push")
    args=ap.parse_args()
    try:
        if os.name!="nt" or str(ROOT).lower() != r"f:\zebra-ganta_ch2".lower():
            raise RuntimeError("Must run on Acer Windows from F:\\zebra-ganta_ch2")
        if git("rev-parse","--show-toplevel").lower().replace("/","\\")!=str(ROOT).lower():
            raise RuntimeError("Git root differs from approved Acer project")
        if git("branch","--show-current")!="main":
            raise RuntimeError("Must be on main")
        # Avoid making a commit containing other changes staged by the operator.
        if git("status","--porcelain","--untracked-files=no"):
            raise RuntimeError("Tracked files have local changes; refusing automatic publish")
        if git("diff","--cached","--name-only"):
            raise RuntimeError("Other staged changes exist; refusing")
        prepared=discover()
        for label,files,manifest,info in prepared:
            dest=TARGET_ROOT/label
            if dest.exists():
                raise RuntimeError(f"Target already exists; refuse overwrite: {dest}")
            print(f"{label}: "+", ".join(f"{n} {inf['rows']} rows SHA256={inf['sha256'][:16]}" for n,inf in info.items()))
        if not args.publish:
            print("PLAN ONLY — 5 original datasets validated. No file changed, nothing pushed.")
            print("To transfer: uv run python tools/publish_acer_raw.py --publish")
            return 0
        print("Publishing only allowlisted original CSV; original manifests stay on Acer.")
        created=[]
        for label,files,manifest,info in prepared:
            dest=TARGET_ROOT/label
            dest.mkdir(parents=True,exist_ok=False)
            for name,blob in files.items():
                (dest/name).write_bytes(blob)
                created.append(str((dest/name).relative_to(ROOT)).replace("\\","/"))
            (dest/"provenance.json").write_bytes(manifest)
            created.append(str((dest/"provenance.json").relative_to(ROOT)).replace("\\","/"))
        git("add","--",*created)
        staged=set(git("diff","--cached","--name-only").splitlines())
        if staged!=set(created):
            raise RuntimeError("Staging scope mismatch; commit and push cancelled")
        commit=git("commit","-m","data: archive original Acer exp003 exp008 exp009 read-only HDD CSV")
        print(commit)
        # Never force or change the branch; any conflict must be resolved manually.
        print(git("push","origin","main"))
        print("SUCCESS: 5 original datasets pushed to origin/main. No T: reads/writes performed.")
        return 0
    except (OSError,ValueError,RuntimeError,UnicodeError,json.JSONDecodeError) as exc:
        print("ERROR:",exc,file=sys.stderr)
        print("No automatic reset/clean attempted. If files were staged, inspect git status before retry.",file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
