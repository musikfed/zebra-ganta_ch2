# Protocols 006–008 (EN): 1 GiB workloads, data islands and HDD mechanics

**Status: proposed only. No measured results yet.** [Russian research protocol](006-008-workloads-extents-mechanics.ru.md) and [Russian book chapter 8](../book/chapter-8-data-islands-mechanics-ru.md).

## 006 — large-file, many-file and concurrent access

Research question: Is Adaptive Macro Interleave beneficial for 1 GiB or larger copies, many smaller files, random selection and competing readers? This is a hypothesis, not an observed speedup.

Test matrix: one contiguous 1 GiB logical object; 4096 × 256 KiB objects with the same total useful data; an archive of the set with compression/metadata overhead accounted for separately; one/two/four independent read streams, sequential and interleaved. Record actual bytes, total time, useful MB/s, p50/p95/p99 latency, exact request order, concurrency, checksums, cache/warm-up and repeated independent runs.

First create synthetic, deterministic **request traces** without disk access. Reading existing user-approved files and copying them are distinct stages. **Never** silently create a 1 GiB dataset or write to the protected HGST T: sample. A file copy is a write operation; it requires a separately approved test volume, verified source/destination and backups. Copy timings from Acer SSD F: are not HGST measurements. A genuine Zebra comparison requires a verified physical layout and an implemented algorithm, not just assumed layout functions from simulate.py.

## 007 — logical extent boundaries versus magnetic tracks

Windows FSCTL_GET_RETRIEVAL_POINTERS exposes allocated file extents by virtual cluster number (VCN) and volume logical cluster number (LCN). It **does not** reveal physical track radii, head locations, servo marks, true magnetic sector boundaries, or internal remapping. Microsoft documentation: https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-fsctl_get_retrieval_pointers.

Future read-only extent inspection may report file offset, VCN, LCN, file-system cluster size, extent boundaries and holes where supported. All graphics must state **logical map only**, and unsupported storage/permissions must fail safely. No file relocation, defragmentation or partition writes.

## 008 — head servo, angular speed and lifetime

Nominal spindle speed 7200 rpm corresponds to 120 revolutions/s, 8.33 ms/revolution and about 754 rad/s. This is a theoretical conversion, not direct measurement. Voice-coil actuator seeking includes acceleration, deceleration and settling; the true angular velocity of the head cannot be derived from host read latency alone. Spindle motor braking during shutdown is distinct from servo-controlled actuator deceleration. Do not alter firmware, power supply, parking or servo control to test speculative acceleration.

Evaluate the whole system: read/seek costs, potential extra migration writes, energy, heat, error rates and SMART availability. Any claimed lifespan improvement requires long-term measurements rather than extrapolation from LBA jumps.

**Publication rule:** technical protocols and summaries in Russian and English; book prose in Russian. All results must be labelled MEASURED, SIMULATED or SCHEMATIC, with source and reproducibility details.

## Acer confirmation: workload 006 plans, not HDD measurements

On 13 November 2026 the author confirmed three deterministic logical workload plans with **1,073,741,824 bytes each**. The `single` trace contains 1,024 × 1 MiB reads; `small-sequential` and `small-interleaved` each contain 4,096 × 256 KiB logical object reads, with the latter using four stream **labels**, not real concurrent I/O. All **22 Python unit tests passed** (0.089 s). This validates the request-trace preparation only; no device benchmark or Zebra acceleration was demonstrated.

For experiment 007, [`tools/inspect_extents007.py`](../../tools/inspect_extents007.py) provides a guarded, default dry-run Windows metadata inspection of a single **explicit existing ordinary file on T:**. Live mode requires an explicit `--run`, checks HGST Disk 2, T:, capacities, NTFS and VIA Labs USB parent, and calls `fsutil file queryextents`. This exposes **logical NTFS allocation extents**, not magnetic sectors, track radii, servo timing or physical head positions. No writes or file-content access are implemented. Real Windows command behavior has not yet been verified; do not bypass failures.


## Acer validation of experiment 007 (13 November 2026)

The author pulled commit `2a1ab3b` and confirmed **24 unit tests passed (0.082 s)**. The default call with example `T:\TestData\sample.bin` returned **PLAN ONLY**, so no volume metadata was actually queried. A root-only, non-hidden file listing returned no entries; this **does not prove the volume is empty**, as subdirectories and hidden/system entries remain unchecked. Next action is limited to read-only enumeration with `Get-ChildItem -LiteralPath T:\ -Force` followed, only if needed, by a bounded display of recursive file entries. Do not publish private filenames, invent extents, or run `--run` on an example nonexistent path. No actual extent-mapping results exist yet.


## HGST T: inventory after experiment 007 preparatory check (13 Nov 2026)

A forced listing of the T: root returned only the hidden/system `System Volume Information` directory. A recursive file listing with `-File -Recurse -Force -ErrorAction SilentlyContinue` returned no entries. **No accessible ordinary files were found for extent mapping** under this enumeration. This does not prove that disk sectors are physically blank or that no inaccessible NTFS metadata exists; errors may have been suppressed. The extent-query `--run` stage **was not executed**. Do not inspect protected system metadata by bypassing permissions.

Next experimental-design stage: an explicitly authorized noncritical test corpus (one 1 GiB file vs 4,096 × 256 KiB files) and read-only NTFS extent mapping **after** a separate, reviewed write protocol. No automatic creation or relocation on T:, no unapproved defragmentation, and no claimed physical tracks.

## Acer D: read-only extent mapping candidate

D: is NTFS on SATA SSD Disk 0 **AMD R5SL120G**, serial **12012221W1021**, disk capacity **120034123776 bytes**, volume capacity **120031539200**, free **107038748672 bytes**, volume status **Healthy**. D: includes pre-existing project directories, applications and archives and must **not** be treated as a disposable test target.

The separate [tools/inspect_extents007d.py](../../tools/inspect_extents007d.py) is a guarded read-only single-file metadata inspector. Default invocation is **PLAN ONLY** with no device queries. Optional `--run` verifies exactly the documented D: disk, serial, NTFS and volume identity, rejects noncanonical paths and links/junctions, and invokes only `fsutil file queryextents`. This reveals filesystem VCN/LCN allocation, not a measured physical track map. No writes, deletes or defragmentation. Windows live validation remains pending; private filenames must not be published.

```powershell
git pull --ff-only origin main
uv run python -m unittest discover -s tests -v
uv run python tools/inspect_extents007d.py --file "D:\tools\sample.bin"
```

Example paths need not exist in PLAN ONLY mode. Do not append `--run` until a specific existing non-sensitive file and the tests have been reviewed.
