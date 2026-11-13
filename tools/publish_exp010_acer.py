#!/usr/bin/env python3
r"""Safely publish original experiment 010 Acer CSV to GitHub.

Default PLAN ONLY; --publish copies original numeric CSV bytes unchanged
and a sanitized provenance.json. Git commit and push only three files.
No physical HDD access. No original hardware manifest exposed.
"""
from __future__ import annotations
import argparse, csv, hashlib, io, json, math, os, statistics, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "results" / "20261113T130425Z-exp010-startup-ntfs"
DEST = ROOT / "data" / "raw" / "exp010-startup-ntfs"
OBS_COLUMNS = ("session","pause_after_open_s","first_offset","second_offset","read_bytes","open_ms","first_read_ms","second_read_ms")
SUMMARY_COLUMNS = ("pause_after_open_s","sessions","median_open_ms","median_first_ms","median_second_ms")
PAUSES = (0,2,10)
MAX_BYTES = 100000

def csv_rows(blob, expected):
    if not blob or len(blob)>MAX_BYTES:
        raise ValueError("CSV missing or too large")
    reader=csv.DictReader(io.StringIO(blob.decode("utf-8-sig"), newline=""))
    if tuple(reader.fieldnames or ())!=expected:
        raise ValueError("Unexpected CSV columns; refusing to upload")
    rows=list(reader)
    if any(None in r or not all(isinstance(v,str) and v.strip() for v in r.values()) for r in rows):
        raise ValueError("Invalid CSV rows")
    return rows

def validate(observation_blob, summary_blob, manifest_blob):
    manifest=json.loads(manifest_blob.decode("utf-8-sig"))
    if not isinstance(manifest,dict) or manifest.get("schema")!="zebra-ganta.exp010.v1" or manifest.get("status")!="complete":
        raise ValueError("Incorrect or incomplete experiment 010")
    if (manifest.get("seed"),manifest.get("sessions"),manifest.get("reads_per_session"),manifest.get("block_bytes"))!=(20261113,9,2,4096):
        raise ValueError("Unexpected original experiment settings")
    if sorted(manifest.get("pauses_after_handle_open_s",[]))!=list(PAUSES):
        raise ValueError("Unexpected pause conditions")
    obs=csv_rows(observation_blob,OBS_COLUMNS)
    sums=csv_rows(summary_blob,SUMMARY_COLUMNS)
    if len(obs)!=9 or len(sums)!=3:
        raise ValueError("Wrong original data row counts")
    grouped={p:[] for p in PAUSES}
    seen=set()
    for idx,row in enumerate(obs,1):
        s=int(row["session"]);p=int(row["pause_after_open_s"])
        a=int(row["first_offset"]);b=int(row["second_offset"])
        size=int(row["read_bytes"])
        latency=[float(row[k]) for k in ("open_ms","first_read_ms","second_read_ms")]
        if s!=idx or p not in PAUSES or size!=4096 or a<=0 or b-a!=2097152 or a%4096 or b%4096:
            raise ValueError("Unexpected session, address or block size")
        if a in seen or b in seen: raise ValueError("Repeated LBA")
        seen.update((a,b))
        if not all(math.isfinite(x) and x>=0 for x in latency):
            raise ValueError("Non-finite or negative latency")
        grouped[p].append(latency)
    if any(len(v)!=3 for v in grouped.values()):
        raise ValueError("Unbalanced pauses")
    if [int(r["pause_after_open_s"]) for r in sums]!=list(PAUSES):
        raise ValueError("Unexpected summary ordering")
    for row in sums:
        p=int(row["pause_after_open_s"])
        if int(row["sessions"])!=3:raise ValueError("Wrong summary session count")
        for j,key in enumerate(("median_open_ms","median_first_ms","median_second_ms")):
            saved=float(row[key])
            if not math.isfinite(saved) or abs(saved-statistics.median(x[j] for x in grouped[p]))>0.000021:
                raise ValueError("Saved summary disagrees with original observations")
    return {
        "schema":"zebra-ganta.exp010-public-archive.v1",
        "experiment":"010",
        "dataset":SRC.name,
        "origin":"original Acer F: CSV, HGST Disk 2, T: NTFS, read-only",
        "original_manifest_sha256":hashlib.sha256(manifest_blob).hexdigest(),
        "seed":20261113,"sessions":9,"pauses_s":list(PAUSES),"reads_per_session":2,
        "files":{name:{"rows":count,"sha256":hashlib.sha256(blob).hexdigest(),"bytes":len(blob)}
                 for name,blob,count in (("observations.csv",observation_blob,9),("summary.csv",summary_blob,3))},
        "limitations":"Windows/USB/HDD latency combined; no spindle-state control or Zebra placement proof",
    }

def git(*args):
    p=subprocess.run(("git",*args),cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    if p.returncode:raise RuntimeError(f"git {args[0]} failed: {p.stderr.strip() or p.stdout.strip()}")
    return p.stdout.strip()

def read_source(name):
    path=SRC/name
    if SRC.is_symlink() or path.is_symlink() or not path.is_file() or path.resolve().parent!=SRC.resolve():
        raise ValueError(f"Unsafe or missing file: {path}")
    data=path.read_bytes()
    if not data or len(data)>MAX_BYTES:raise ValueError("Unexpected source file size")
    return data

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish",action="store_true")
    args=parser.parse_args()
    try:
        if os.name!="nt" or str(ROOT).lower()!=r"f:\zebra-ganta_ch2":
            raise RuntimeError("Run only on Windows Acer from F:\\zebra-ganta_ch2")
        if git("rev-parse","--show-toplevel").replace("/","\\").lower()!=str(ROOT).lower() or git("branch","--show-current")!="main":
            raise RuntimeError("Git working directory or branch does not match")
        if git("status","--porcelain","--untracked-files=no") or git("diff","--cached","--name-only"):
            raise RuntimeError("Local tracked or staged changes exist; refusing")
        if DEST.exists():raise RuntimeError("Archive already exists; no overwrite allowed")
        raw_obs=read_source("observations.csv")
        raw_summary=read_source("summary.csv")
        manifest=read_source("manifest.json")
        provenance=validate(raw_obs,raw_summary,manifest)
        for name,metadata in provenance["files"].items():
            print(f"{name}: {metadata['rows']} rows; SHA256={metadata['sha256']}")
        if not args.publish:
            print("PLAN ONLY — original 010 data validated. No files changed or pushed.")
            return 0
        DEST.mkdir(parents=True,exist_ok=False)
        files={"observations.csv":raw_obs,"summary.csv":raw_summary,
               "provenance.json":(json.dumps(provenance,ensure_ascii=False,indent=2)+"\n").encode("utf-8")}
        paths=[]
        for name,data in files.items():
            (DEST/name).write_bytes(data)
            paths.append(str((DEST/name).relative_to(ROOT)).replace("\\","/"))
        git("add","--",*paths)
        if set(git("diff","--cached","--name-only").splitlines())!=set(paths):
            raise RuntimeError("Unexpected staged paths; no commit performed")
        print(git("commit","-m","data: archive original Acer exp010 startup NTFS read-only CSV"))
        print(git("push","origin","main"))
        print("SUCCESS: original 010 CSV uploaded. No HDD T: access.")
        return 0
    except (ValueError,RuntimeError,OSError,UnicodeError,json.JSONDecodeError) as err:
        print("ERROR:",err,file=sys.stderr)
        print("If commit succeeded but push failed, run ONLY git push origin main.",file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
