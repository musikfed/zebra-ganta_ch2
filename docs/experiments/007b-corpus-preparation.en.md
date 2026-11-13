# Stage 007B — controlled corpus design for Zebra Ganta

**STATUS: PLAN ONLY. No writes authorized.** This intermediate stage sits between the existing 007 NTFS metadata work and 008 actuator/lifetime research. [Russian protocol](007b-corpus-preparation.ru.md).

## Corpus matrix

| Workload | File count | Size per file | Useful data |
|---|---:|---:|---:|
| Single file | 1 | 1 GiB | 1 GiB |
| Small files | 4096 | 256 KiB | 1 GiB |
| Archive of small files | 1 | Unknown until compression and format are chosen | 1 GiB original, archive bytes must be measured separately |

The current read-only HGST T: volume has no ordinary accessible files under the previous enumeration. Do **not** create files on T: to enable a convenient benchmark. A separate, deliberately selected disposable test volume and **explicit subsequent authorization** are required before any creation, relocation, removal or overwriting. A cautious initial space budget of 4 GiB is used for planning only, not as a guarantee of real allocation.

Run the metadata-free planner:

```powershell
git pull --ff-only origin main
uv run python tools/plan_corpus007b.py
uv run python tools/plan_corpus007b.py --target hgst-t
uv run python -m unittest discover -s tests -v
```

The `--target hgst-t` flag is only a hypothetical label. The returned plan always has `target_approved_for_writes=false` and `generator_implemented=false`. No device enumeration, physical disk operations or file creation occur.

## Requirements before an actual test

A disposable verified test volume; free-space inventory and backup; fail-closed path restrictions; explicit approval; non-repetitive payload patterns; per-file SHA-256 and aggregate manifest; time/cost of data generation and compression counted separately; independent cold/warm read trials; sequential and multi-stream workloads; NTFS VCN/LCN extent maps; comparable useful byte counts and a complete record of writes.

The existing `simulate.py` models *assumed* allocations; it does not implement on-disk Adaptive Macro Interleave. A genuine baseline vs Zebra speedup claim requires **two independently verified physical layouts** with reproducible workloads, not labels alone.

**No 007B performance measurement has been conducted.**
