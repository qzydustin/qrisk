"""Contracts of qrisk.tokens.

The expected values are the tokens of real report files under data/, pinned
so that the normalization never drifts.
"""

import json

import pytest
from qiskit import QuantumCircuit, qpy
from qiskit.circuit import Parameter

from qrisk.paths import ARTIFACTS_DIR, CANDIDATE_GROUPS_DIR, VERIFIED_DIR
from qrisk.tokens import (
    asap_moments, canonical_key, circuit_tokens, count_contiguous, pattern_has_cz,
    structural_key, token_from_report_gate, tokens_match,
)

# (report root, group, report file under <group>/ddmin_reports)
FEZ_130 = (ARTIFACTS_DIR, "grover3-fez-O3-130_131_132_138", "fez_20260506_193027.json")
FEZ_100 = (CANDIDATE_GROUPS_DIR, "grover3-fez-O3-100_101_102_116", "fez_20260520_155244.json")
KINGSTON_CLEANED = (ARTIFACTS_DIR, "grover3-kingston-O3-126_127_128_137", "kingston_20260617_201657.json")
FEZ_97_OLD = (VERIFIED_DIR, "grover3-fez-O3-97_106_107_108", "ibm_fez_20251115_143208.json")
MARRAKESH_OLD = (VERIFIED_DIR, "marrakesh_6_7_8_17", "ibm_marrakesh_20251118_102315.json")

HALF_PI = 1.570796
RZ_SX_RZ_X4 = (
    "rz(Q0) → rz(Q1) → rz(Q2) → rz(Q3) → sx(Q0) → sx(Q1) → sx(Q2) → sx(Q3) "
    "→ rz(Q0) → rz(Q1) → rz(Q2) → rz(Q3)"
)

REPORT_CASES = [
    # NEW schema, `pattern` list form
    (FEZ_130, "pattern",
     [("cz", (130, 131), ()), ("x", (130,), ()), ("rz", (130,), (-2.748894,)),
      ("sx", (131,), ()), ("rz", (131,), (1.583529,))],
     "cz(130,131) → sx(131) → x(130) → rz(130) → rz(131)",
     "cz(Q0,Q1) → sx(Q1) → x(Q0) → rz(Q0) → rz(Q1)", True),
    # NEW schema, `segments_info` dicts keyed "operation"; same gates in circuit order
    (FEZ_130, "segment",
     [("cz", (130, 131), ()), ("x", (130,), ()), ("sx", (131,), ()),
      ("rz", (130,), (-2.748894,)), ("rz", (131,), (1.583529,))],
     "cz(130,131) → sx(131) → x(130) → rz(130) → rz(131)",
     "cz(Q0,Q1) → sx(Q1) → x(Q0) → rz(Q0) → rz(Q1)", True),
    # Same shape on other physical qubits
    (FEZ_100, "pattern",
     [("cz", (100, 101), ()), ("x", (100,), ()), ("rz", (100,), (-2.748894,)),
      ("sx", (101,), ()), ("rz", (101,), (1.583529,))],
     "cz(100,101) → sx(101) → x(100) → rz(100) → rz(101)",
     "cz(Q0,Q1) → sx(Q1) → x(Q0) → rz(Q0) → rz(Q1)", True),
    # Force-cleaned report: the motif survives under _clean_override.original
    (KINGSTON_CLEANED, "original",
     [("rz", (126,), (HALF_PI,)), ("sx", (126,), ()), ("rz", (126,), (HALF_PI,)),
      ("rz", (127,), (HALF_PI,)), ("sx", (127,), ()), ("rz", (127,), (HALF_PI,)),
      ("rz", (128,), (HALF_PI,)), ("sx", (128,), ()), ("rz", (128,), (HALF_PI,)),
      ("rz", (137,), (HALF_PI,)), ("sx", (137,), ()), ("rz", (137,), (-HALF_PI,))],
     "rz(126) → rz(127) → rz(128) → rz(137) → sx(126) → sx(127) → sx(128) → sx(137) "
     "→ rz(126) → rz(127) → rz(128) → rz(137)",
     RZ_SX_RZ_X4, False),
    # OLD schema dicts keyed "op"
    (FEZ_97_OLD, "details",
     [("rz", (106,), (-1.963495,)), ("cz", (97, 107), ()), ("sx", (106,), ()), ("x", (97,), ()),
      ("sx", (107,), ()), ("rz", (106,), (-4.712389,)), ("rz", (97,), (-1.570796,)),
      ("rz", (107,), (2.748894,))],
     "cz(97,107) → rz(106) → sx(106) → sx(107) → x(97) → rz(106) → rz(107) → rz(97)",
     "cz(Q0,Q1) → rz(Q2) → sx(Q2) → sx(Q1) → x(Q0) → rz(Q2) → rz(Q1) → rz(Q0)", True),
    # OLD schema with a reversed cz: the token keeps (7, 6), the keys sort it
    (MARRAKESH_OLD, "details",
     [("rz", (6,), (3.141593,)), ("sx", (7,), ()), ("rz", (7,), (HALF_PI,)), ("cz", (7, 6), ())],
     "rz(6) → sx(7) → rz(7) → cz(6,7)",
     "rz(Q0) → sx(Q1) → rz(Q1) → cz(Q0,Q1)", True),
]


def _report_gates(report, source):
    root, group, name = report
    d = json.loads(root.joinpath(group, "ddmin_reports", name).read_text())
    if source == "pattern":
        return d["pattern"]
    if source == "original":
        return d["_clean_override"]["original"]["pattern"]
    if source == "details":
        return d["problematic_details"][0]["instructions"]
    flagged = d["problematic_segments"][0]
    return next(s for s in d["segments_info"] if s["layer_id"] == flagged)["instructions"]


@pytest.mark.parametrize("report,source,tokens,key,shape,has_cz", REPORT_CASES)
def test_report_gates(report, source, tokens, key, shape, has_cz):
    gates = _report_gates(report, source)
    toks = [token_from_report_gate(g) for g in gates]
    assert toks == tokens
    assert canonical_key(toks) == key
    assert structural_key(key) == shape
    assert pattern_has_cz(toks) is has_cz
    if source in ("pattern", "original"):     # the raw list form must key the same way
        assert canonical_key(gates) == key


def test_asap_moments_group_parallel_gates():
    gates = _report_gates(FEZ_130, "pattern")
    assert asap_moments(gates) == [("cz(130,131)",), ("sx(131)", "x(130)"), ("rz(130)", "rz(131)")]
    assert asap_moments([]) == [] and canonical_key([]) == "" and structural_key("") is None


def test_circuit_tokens():
    with open(CANDIDATE_GROUPS_DIR.joinpath("grover3-fez-O3-46_47_48_57", "base_3x.qpy"), "rb") as f:
        circ = qpy.load(f)[0]
    toks = circuit_tokens(circ)
    assert (len(circ.data), len(toks)) == (440, 429)      # barriers and measures skipped
    assert toks[:10] == [
        ("rz", (46,), (HALF_PI,)), ("sx", (46,), ()), ("rz", (46,), (HALF_PI,)),
        ("rz", (47,), (HALF_PI,)), ("sx", (47,), ()), ("rz", (47,), (HALF_PI,)),
        ("rz", (48,), (HALF_PI,)), ("sx", (48,), ()), ("rz", (48,), (HALF_PI,)),
        ("rz", (57,), (HALF_PI,)),
    ]
    assert toks[43:51] == [
        ("rz", (47,), (-2.748894,)), ("sx", (47,), ()), ("sx", (48,), ()), ("rz", (48,), (-1.19083,)),
        ("cz", (48, 47), ()), ("sx", (47,), ()), ("rz", (47,), (-2.748894,)), ("sx", (47,), ()),
    ]
    assert count_contiguous(toks, toks[46:49]) == 3


def test_unbound_parameter_kept_as_str():
    qc = QuantumCircuit(1)
    qc.rz(Parameter("theta"), 0)
    assert circuit_tokens(qc) == [("rz", (0,), ("theta",))]


def test_tokens_match_tolerance_and_direction():
    assert tokens_match(("rz", (1,), (0.1,)), ("rz", [1], (0.100009,)))
    assert not tokens_match(("rz", (1,), (0.1,)), ("rz", (1,), (0.10002,)))
    assert not tokens_match(("cz", (0, 1), ()), ("cz", (1, 0), ()))
