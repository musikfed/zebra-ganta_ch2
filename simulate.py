#!/usr/bin/env python3
"""Synthetic, explicit-cost simulator. No physical-disk access.

Three allocations are *models*, NOT installed HDD filesystems:
baseline, fixed macrostripe, heuristic adaptive macrostripe.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import random
import statistics

MIB = 1024*1024
DISK_BYTES = 500_106_780_160
MODEL_ONLY = "SYNTHETIC MODEL — NEVER PRESENT AS MEASURED HDD DATA"


def workload(seed: int, n: int, hot_share: float):
    """Reproducible logical requests; no claims about real workload distribution."""
    rng=random.Random(seed)
    requests=[]
    for _ in range(n):
        hot = rng.random()<hot_share
        object_id = rng.randrange(12 if hot else 12, 512)
        length = rng.choice((4,16,64,256))*1024
        requests.append((object_id,length))
    return requests


def stripe_size(seek_ms: float, throughput_mbs: float, k: float):
    """Hypothesis B >= k*T*V; B in bytes, T seconds, V bytes/second."""
    if seek_ms<=0 or throughput_mbs<=0 or k<=0:
        raise ValueError("model parameters must be positive")
    raw = k*(seek_ms/1000)*(throughput_mbs*1_000_000)
    return max(MIB, int((raw+MIB-1)//MIB)*MIB)


def address_for(object_id, placement, stripe_bytes):
    # These formulas represent hypothetical layouts. No actual writes happen.
    if placement=="baseline":
        # Hash gives a deterministic scattered synthetic layout, deliberately
        # not a claim about how NTFS allocates files.
        return ((object_id*2654435761) % 1_000_003)*DISK_BYTES//1_000_003
    if placement=="fixed":
        band=(object_id%16)
        slot=(object_id//16)
        return (band*DISK_BYTES//16 + slot*stripe_bytes) % DISK_BYTES
    if placement=="adaptive":
        # Group hot identifiers together as an explicitly assumed oracle:
        # not a fair real-world algorithm unless hotness is learned from TRAIN ONLY.
        if object_id<12:
            return (object_id*stripe_bytes) % DISK_BYTES
        return (DISK_BYTES//4 + (object_id-12)*stripe_bytes) % DISK_BYTES
    raise ValueError("unknown placement")


def score(requests, placement, stripe_bytes, seek_ms, throughput_mbs):
    """Toy cost = seek_ms*(LBA gap / disk size) + bytes/throughput;
    ignores rotation, caching, command queue, zone bit recording and USB.
    """
    position=0
    total=0.
    seek_total=0.
    transfer_total=0.
    transitions=[]
    for obj,length in requests:
        at=address_for(obj,placement,stripe_bytes)
        distance=abs(at-position)
        seek=seek_ms*(distance/DISK_BYTES)
        transfer=length/(throughput_mbs*1_000_000)*1000
        total+=seek+transfer
        seek_total+=seek
        transfer_total+=transfer
        transitions.append(distance)
        position=at
    return {"total_model_ms":round(total,4), "travel_model_ms":round(seek_total,4),
            "transfer_model_ms":round(transfer_total,4),
            "mean_jump_fraction":round(statistics.mean(transitions)/DISK_BYTES,5)}


def evaluate(seed, count, hot_share, seek_ms, throughput_mbs, k, fixed_mib):
    if not (0<=hot_share<=1 and 100<=count<=100_000):
        raise ValueError("invalid workload size/hot_share")
    adaptive=stripe_size(seek_ms,throughput_mbs,k)
    # Workload and hot objects are explicit assumptions, not derived from experiment.
    req=workload(seed,count,hot_share)
    variants=(("baseline",fixed_mib*MIB),("fixed",fixed_mib*MIB),("adaptive",adaptive))
    output=[]
    for name,b in variants:
        s=score(req,name,b,seek_ms,throughput_mbs)
        output.append({"placement":name, "stripe_mib":round(b/MIB,4), **s})
    return {"meta":{"status":MODEL_ONLY,"seed":seed,"requests":count,
        "assumed_hot_share":hot_share,"assumed_seek_ms":seek_ms,
        "assumed_throughput_MB_s":throughput_mbs,"hypothesis_k":k,
        "fixed_mib":fixed_mib,"note":"Baseline is a hash layout, NOT real NTFS. Adaptive knows hot-id set by assumption. Comparisons are illustrative and may advantage adaptive."},
        "results":output}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed",type=int,default=42)
    p.add_argument("--requests",type=int,default=5000)
    p.add_argument("--hot-share",type=float,default=.75)
    p.add_argument("--seek-ms",type=float,default=12)
    p.add_argument("--mb-s",type=float,default=38)
    p.add_argument("--k",type=float,default=4)
    p.add_argument("--fixed-mib",type=int,default=64)
    p.add_argument("--out",default="results/simulation")
    a=p.parse_args()
    if not (0<a.fixed_mib<=1024):
        p.error("--fixed-mib must be 1..1024")
    try:
        data=evaluate(a.seed,a.requests,a.hot_share,a.seek_ms,a.mb_s,a.k,a.fixed_mib)
    except ValueError as exc:
        p.error(str(exc))
    target=Path(a.out).resolve()
    if target.drive.upper()=="T:":
        p.error("Never write results to HGST T:")
    target.mkdir(parents=True,exist_ok=True)
    (target/"model.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    with (target/"model.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=list(data["results"][0]))
        w.writeheader();w.writerows(data["results"])
    print(MODEL_ONLY)
    for r in data["results"]:
        print(f'{r["placement"]:10s}  cost={r["total_model_ms"]:.2f} assumed-ms  stripe={r["stripe_mib"]} MiB')
    print("Saved:",target)
    print("No real HDD I/O and NO claimed performance gain.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
