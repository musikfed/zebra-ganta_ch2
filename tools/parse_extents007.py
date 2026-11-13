"""Pure parser for Windows fsutil file queryextents text.

The numeric fields are ASCII, even on Russian Windows (where the length
field label is OEM-encoded). Parse as bytes to avoid console mojibake.
LCN FFFFFFFFFFFFFFFF denotes an unallocated / sparse logical run.
A run can represent NTFS compression padding; inspect attributes to confirm.
"""
from __future__ import annotations
import re

ROWS = re.compile(
    rb"(?m)^\s*VCN:\s*0x([0-9a-fA-F]+)\s+[^\r\n]*?:\s*0x([0-9a-fA-F]+)\s+LCN:\s*0x([0-9a-fA-F]+)\s*$"
)
HOLE_LCN = (1 << 64) - 1


def parse_extents(raw: bytes) -> dict:
    if not isinstance(raw, bytes):
        raise TypeError("Expected raw bytes from fsutil")
    rows=[]
    for match in ROWS.finditer(raw):
        start, length, lcn = (int(x,16) for x in match.groups())
        if length <= 0:
            raise ValueError("Zero-length NTFS run")
        if rows and start != rows[-1]["vcn_end"]:
            raise ValueError("Gap/overlap in logical VCN ranges; incomplete map")
        if not rows and start != 0:
            raise ValueError("Mapping does not start at VCN zero")
        rows.append({"vcn_start":start,"vcn_end":start+length,"clusters":length,
                     "lcn":None if lcn==HOLE_LCN else lcn})
    if not rows:
        raise ValueError("No parsable VCN/LENGTH/LCN rows; check fsutil output")
    allocated=[r for r in rows if r["lcn"] is not None]
    holes=[r for r in rows if r["lcn"] is None]
    # Number of discontinuities between consecutive allocated runs only.
    discontinuities=sum(
        b["lcn"] != a["lcn"]+a["clusters"]
        for a,b in zip(allocated,allocated[1:])
    )
    return {
        "kind": "MEASURED_LOGICAL_NTFS_EXTENTS",
        "run_count":len(rows),"allocated_run_count":len(allocated),
        "unallocated_run_count":len(holes),
        "logical_clusters":rows[-1]["vcn_end"],
        "allocated_clusters":sum(r["clusters"] for r in allocated),
        "unallocated_clusters":sum(r["clusters"] for r in holes),
        "lcn_discontinuities_between_allocated_runs":discontinuities,
        "allocated_lcn_contiguous":discontinuities==0 and bool(allocated),
        "first_allocated_lcn":allocated[0]["lcn"] if allocated else None,
        "end_allocated_lcn_exclusive":allocated[-1]["lcn"]+allocated[-1]["clusters"] if allocated else None,
        "runs":rows,
        "caveat": "NTFS logical cluster map; holes can be compression/sparse; "
                  "does not reveal flash mapping or magnetic geometry.",
    }
