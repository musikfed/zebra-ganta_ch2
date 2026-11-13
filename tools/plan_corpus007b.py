#!/usr/bin/env python3
"""Zebra Ganta 007B: SAFE corpus design. NEVER reads or writes a disk.

РУС: Только расчёт и паспорт будущих тестовых файлов. Никаких операций с
файловой системой, даже опроса её свободного пространства.
EN: Dry-run planning only, not a dataset creator or an HDD benchmark.
"""
from __future__ import annotations

import argparse
import json

MIB = 1024 * 1024
GIB = 1024 * MIB
SMALL_FILE_BYTES = 256 * 1024
SMALL_COUNT = 4096
TEST_DATA_BYTES = GIB
# Conservative capacity budget for baseline, small-file and temporary output;
# true physical allocation and compression may differ.
RECOMMENDED_FREE_BYTES = 4 * GIB
SAFETY_LABEL = "PLAN_ONLY_NO_DISK_IO"


def make_plan(target: str, include_archive: bool = True) -> dict:
    if target not in ("separate-test-volume", "hgst-t"):
        raise ValueError("target must be separate-test-volume or hgst-t")
    if SMALL_FILE_BYTES * SMALL_COUNT != TEST_DATA_BYTES:
        raise AssertionError("The two corpus layouts must contain equal useful data")
    variants = [
        {"name": "large-file", "files": 1, "bytes_per_file": GIB,
         "useful_bytes": GIB},
        {"name": "small-files", "files": SMALL_COUNT,
         "bytes_per_file": SMALL_FILE_BYTES, "useful_bytes": GIB},
    ]
    if include_archive:
        variants.append({
            "name": "archive-of-small-files",
            "files": 1,
            "bytes_per_file": None,
            "useful_bytes": GIB,
            "archive_bytes": "UNKNOWN until format/compression chosen",
        })
    return {
        "status": SAFETY_LABEL,
        "selected_target": target,
        "target_approved_for_writes": False,
        "generator_implemented": False,
        "physical_access": False,
        "nominal_data_bytes_per_variant": TEST_DATA_BYTES,
        "variants": variants,
        "minimum_prudent_free_space_bytes": RECOMMENDED_FREE_BYTES,
        "baseline_vs_zebra_layout_verified": False,
        "file_checksums_measured": False,
        "planned_integrity": "Record per-file SHA-256 and aggregate manifest after future authorized creation",
        "planned_controls": [
            "Identify an independent, disposable test volume by serial/size/drive letter",
            "Never write to HGST T: under the current read-only experimental policy",
            "Record pre-test SMART/temperature if accessible; do not bypass access errors",
            "Never overwrite or delete preexisting files; use isolated empty namespace",
            "Separate data generation, archive/compression and read benchmark timings",
            "Measure cold/warm reads separately and log exact access order",
            "Map logical NTFS extents after file creation (not magnetic tracks)",
            "Document workload, repeated independent runs and total write amplification",
            "Require an explicit future protocol and operator approval before any writes",
        ],
        "warning": "No disk probed; no bytes generated, read, written, deleted or moved. "
                   "This is not a speed or durability measurement.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target", choices=["separate-test-volume", "hgst-t"],
                   default="separate-test-volume",
                   help="Only a hypothetical target label; no drive is opened")
    p.add_argument("--no-archive", action="store_true")
    a = p.parse_args()
    print(json.dumps(make_plan(a.target, not a.no_archive),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
