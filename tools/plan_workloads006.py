#!/usr/bin/env python3
"""Experiment 006: deterministic LOGICAL workload traces; NO DISK ACCESS.

English: model-only workload planner, NOT a real HDD benchmark.
Русский: создаёт план запросов в памяти, не создаёт файлы и не читает HDD.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random

MIB = 1024 * 1024
KIB = 1024
TOTAL = 1024 * MIB
SMALL_COUNT = 4096
SMALL_BYTES = 256 * KIB
READ_BYTES = MIB
STATUS = "SYNTHETIC REQUEST PLAN — NO PHYSICAL HDD MEASUREMENTS"


def build_workload(scenario: str, streams: int = 1, seed: int = 20261113):
    """Generate exactly 1 GiB of requested logical bytes in bounded memory."""
    if scenario not in ("single", "small-sequential", "small-interleaved"):
        raise ValueError("unsupported scenario")
    if streams not in (1, 2, 4):
        raise ValueError("streams must be 1, 2, or 4")
    if not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed out of range")
    requests = []
    if scenario == "single":
        for offset in range(0, TOTAL, READ_BYTES):
            requests.append({"object": 0, "offset": offset, "bytes": READ_BYTES})
    else:
        for obj in range(SMALL_COUNT):
            requests.append({"object": obj, "offset": 0, "bytes": SMALL_BYTES})
        if scenario == "small-interleaved":
            random.Random(seed).shuffle(requests)
    for index, request in enumerate(requests):
        request["stream"] = index % streams
        request["sequence"] = index
    assert sum(r["bytes"] for r in requests) == TOTAL
    # This is not a wall-clock overlap simulation. Streams are labels for
    # future load generators; actual concurrency remains UNMEASURED.
    return requests


def describe(scenario: str, streams: int = 1, seed: int = 20261113):
    rows = build_workload(scenario, streams, seed)
    # Compare identical logical bytes, not copies or measured HDD speeds.
    encoded = "\n".join(
        f"{r['sequence']},{r['object']},{r['offset']},{r['bytes']},{r['stream']}"
        for r in rows
    ).encode("ascii")
    return {
        "status": STATUS,
        "scenario": scenario,
        "seed": seed,
        "streams": streams,
        "logical_total_bytes": TOTAL,
        "logical_total_GiB": 1,
        "requests": len(rows),
        "distinct_objects": len({r["object"] for r in rows}),
        "request_bytes": list(sorted({r["bytes"] for r in rows})),
        "trace_sha256": hashlib.sha256(encoded).hexdigest(),
        "first_8_requests": rows[:8],
        "limitations": [
            "Objects/streams are logical identifiers, not existing files",
            "No file allocation, head movement, cache or USB I/O measured",
            "Archive compression and file-system metadata not simulated",
            "No performance or Zebra algorithm speedup implied"
        ]
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scenario",choices=["single","small-sequential","small-interleaved"],
                   default="single")
    p.add_argument("--streams",type=int,choices=[1,2,4],default=1)
    p.add_argument("--seed",type=int,default=20261113)
    a=p.parse_args()
    print(json.dumps(describe(a.scenario,a.streams,a.seed),
                     ensure_ascii=False,indent=2))
    print("READ-ONLY PLAN: no files created; no physical disk opened.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
