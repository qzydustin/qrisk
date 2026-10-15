# QRisk

Code and hardware data of the QRisk paper.

QRisk partitions a compiled quantum circuit into moment-based segments and runs DDMin with the oracle **R = TVD(ideal, real) / TVD(ideal, noisy)** to isolate the segments where real hardware is worse than the noise model predicts (R > 1 + τ, τ calibrated from shot noise). Patterns that are rediscovered across calibration windows are stored and broken by commuting gate swaps.

## Layout

| Path | Contents |
|---|---|
| `qrisk/` | The library: moment segmentation (`partition.py`), DDMin (`ddmin.py`), circuit execution on simulators, IBM hardware or an offline emulation (`executor.py`, `ibm_runtime.py`), gate tokens and pattern keys (`tokens.py`), qubit-timeline matching and commuting swaps (`patterns.py`), the Grover-3 workload (`circuits.py`), QPU budget ledger (`budget.py`), TVD and Hellinger (`metrics.py`), config loading (`config.py`), data layout (`paths.py`). `python -m qrisk.cli` runs DDMin on one group. |
| `scripts/grover/` | Compile Grover-3 for every (backend, layout) group and run DDMin on IBM hardware. |
| `scripts/verify/` | Verify sets: commuting-swap variants of a group's circuit binned by pattern hits, bucket top-up, hardware runs. |
| `scripts/xalg/` | Cross-algorithm experiments (section below). |
| `scripts/calibration/` | Historical calibration snapshots of a gate's error rate and the drift plot. |
| `scripts/ibm_accounts.py` | Remaining quota per IBM account; cancel pending jobs. |
| `scripts/smoke_test.py` | Executor smoke test on a Bell circuit (offline unless `--real`). |
| `data/` | Every DDMin run, verify set and cross-algorithm run behind the paper ([data/README.md](data/README.md)). |
| `config/` | `quantum_config.example.json`; copy it to `config/quantum_config.json` and add your IBM account. |
| `tests/` | Unit tests; they run offline. |

## Setup

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
source .venv/bin/activate
python -m pytest
```

Every command runs from the repository root as a module (`python -m ...`), which is what puts `qrisk` and `scripts` on the import path.

## Run DDMin

```bash
python -m qrisk.cli --algorithm grover3-marrakesh-O3-6_7_8_17 --test-mode
```

runs DDMin on `data/artifacts/grover3-marrakesh-O3-6_7_8_17` with the noisy simulator standing in for the device. It connects to IBM Quantum (`config/quantum_config.json`) for the backend and its noise model, and writes the report JSON into the group directory. Without `--test-mode` the oracle runs on the device.

- Discovery: `python -m scripts.grover.generate_and_run_grover3` compiles the Grover-3 groups and runs DDMin on each (`scripts/grover/run_all_ddmin.sh` runs the three backends in parallel).
- Verify sets: `python -m scripts.verify.generate_verify_variants --group <group> --auto-pattern` builds the hit-count buckets; `python -m scripts.verify.run_verify_batch --verify-dir <group>/variants/verify` runs them on hardware (`--dry-run` only checks that every stored circuit resolves).
- Calibration drift: `python -m scripts.calibration.fetch_calibration_drift`.

## Cross-algorithm experiments

Question: are the patterns QRisk isolates from Grover specific to Grover, or do other algorithms compiled onto the same physical qubits expose the same patterns?

| Step | Module | QPU |
|---|---|---|
| 0 | `scripts.xalg.backends`: quota, backend queues | none |
| 1 | `scripts.xalg.prepare`: compile Grover + 13 MQT Bench algorithms on 2 layouts, simulator preflight | none |
| 2 | `scripts.xalg.probe`: one job to measure QPU seconds per circuit | ~5–10 s |
| 3 | `scripts.xalg.ddmin`: **Exp 1**, DDMin on Grover + AE, QPE, QWalk, Random (2 layouts × 2 runs) | most of the budget |
| 4 | `scripts.xalg.variants --plan`: build dose-response variants of Grover's pattern inside other algorithms | none |
| 5 | `scripts.xalg.variants --run`: **Exp 2**, one batched job per algorithm | ~5–10 min |

`scripts/xalg/run_all.sh` runs steps 1–5 and asks before every QPU step.

IBM credentials: sign in at https://quantum.cloud.ibm.com, create an API key, copy the instance CRN, and add the account to `config/quantum_config.json` (start from `config/quantum_config.example.json`): `token` = the API key, `instance` = the CRN, `channel` stays `ibm_cloud`. With several accounts the one with the most remaining quota is used.

```bash
RESULTS_DIR=/tmp/xalg_dryrun HARDWARE=emulate RUNS=1 bash scripts/xalg/run_all.sh ibm_fez   # offline dry run, ~6 min
python -m scripts.xalg.backends                                                          # pick the backend with the shortest queue
RESULTS_DIR=<new dir> bash scripts/xalg/run_all.sh ibm_fez                               # real run, 40 min QPU cap by default
```

Emulated "hardware" is the fake backend's noise model plus an extra 8% error on Grover's busiest cz pair; DDMin should localize that pair for most algorithms on the first layout. Without `RESULTS_DIR` the results go to `data/results/xalg/`, which holds the stored run; step 1 rewrites `circuits/` in the results directory.

Knobs (environment variables): `BUDGET_MIN` (total QPU cap, default 40), `EXP2_RESERVE_MIN` (kept for Exp 2, default 12), `RUNS` (DDMin runs per layout/algorithm, default 2), `PARALLEL` (DDMin runs in flight, default 4), `RESULTS_DIR`.

Budget: every hardware job is checked before submission against `<results>/qpu_ledger.jsonl`, which holds the measured QPU seconds of every job so far and persists across scripts and restarts. A job is refused if `spent + in-flight + estimate > cap`; Exp 1 also refuses to start a DDMin run it cannot plausibly finish. Overshoot is at most the measurement error of one job's estimate. Queue waiting time is not QPU time; `PARALLEL` overlaps the waits, and on a paid plan `--session` on `scripts.xalg.ddmin` keeps one session open. Ctrl-C is safe: finished DDMin runs and variant sets are saved and the same command continues; raising the cap later lets a stopped run continue.

Method: Grover is re-run together with the other algorithms, so every pattern compared comes from one calibration window. Segment 0 is never a DDMin candidate (`--no-protect-first-segment` lets DDMin select it). τ = max(0, …). Patterns are matched on qubit timelines (`qrisk/patterns.py`): an occurrence has the pattern's gates consecutive and in order on each qubit's timeline, ignoring the linear order of gates on disjoint qubits and the rz parameters; the linear matcher is reported alongside. Variants differ only by commuting swaps, are checked for unitary equivalence and an identical gate multiset, and include the untouched compiled circuit. Raw counts of every oracle call are saved, so TVD and Hellinger can both be reported; every report records the package versions under `versions`.

Outputs under `<results>/`: `circuits/<backend>/preflight.json` (compiled sizes, non-uniformity, model error vs. floor), `ddmin/<backend>/<layout>/<algorithm>/runN.json` (DDMin reports with raw counts), `variants/<backend>/<layout>/<algorithm>/{manifest,summary}.json` (Exp 2), `qpu_ledger.jsonl` (QPU seconds per job).
