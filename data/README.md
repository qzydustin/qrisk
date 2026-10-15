# data/

Every hardware run behind the paper. Nothing here is edited by the code; the drivers under `scripts/` write new runs next to the existing ones.

## Layout

| Path | Contents |
|---|---|
| `artifacts/grover3-<backend>-O3-<layout>/` | 30 compile groups (10 per backend, `<layout>` = three measured qubits and the ancilla, optimization level 3), each with `base.qpy` (one Grover iteration). 22 also hold `ddmin_reports/*.json`: the 177 DDMin reports of the long-term study. The other 8 groups were run under `candidate_groups/` or `verified/`. |
| `candidate_groups/grover3-<backend>-O3-<layout>/` | 6 groups: `base_1x.qpy`, `base_3x.qpy` (one and three Grover iterations; DDMin runs on `base_3x`) and `ddmin_reports/` (46 reports). |
| `verified/<layout>/` | The two verified layouts, fez 97,106,107,108 and marrakesh 6,7,8,17: `bad_pattern_memory.json` (the pattern DB the verify sets were generated and scored with), `base_1x.qpy`, `base_3x.qpy`, `variant_properties.json`, `ddmin_reports/` (35 reports), and the dose-response sets `variants/verify*/` (`selection_manifest.json`, `hit_0/`–`hit_3/` circuits, `summary.json` with 40 observations each). `verify_kingston` is layout 97,106,107,108 run on ibm_kingston as the control. |
| `results/xalg/` | The cross-algorithm run on ibm_fez (one calibration window): `circuits/` (compiled workloads and `preflight.json`), `ddmin/<backend>/<layout>/<algorithm>/runN.json` (16 DDMin reports with the raw counts of every oracle call), `qpu_ledger.jsonl` (QPU seconds per job). File formats are listed in the README's cross-algorithm section. |

258 DDMin reports in all; 205 return candidate segments and 53 stop at the baseline.

## DDMin reports
Reports written since 2026-05 (`meta.timestamp`, `meta.evaluation` with shots, `noise_threshold`, `min_expected_tvd`; `problematic_segments`; `pattern` as `[op, [qubits], [params]]` tokens; `segments_info`; `ddmin_log`) are the schema `qrisk/ddmin.py` writes today. The 20 reports from 2025-11 to 2026-04 use the older layout: `timestamp`, `baseline_ratio`, `noise_threshold` at the top level, and one `problematic_details[i].instructions` list per flagged segment.

Reports whose only flagged fragment is the rz-sx-rz single-qubit motif (no cz) have `problematic_segments` and `pattern` cleared; the values as returned by DDMin are kept under `_clean_override.original`.

## Verify manifests
`qpy_path` and `base_circuit` in a `selection_manifest.json` are resolved by `qrisk.paths.resolve_stored` (as given, then relative to `data/`, then `<manifest dir>/<bucket>/<file>`); `run_verify_batch.py --dry-run` checks that every entry resolves. Manifests written by the current scripts hold paths relative to `data/`.
