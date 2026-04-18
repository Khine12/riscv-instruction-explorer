"""
Unit tests for the RISC-V Instruction Set Explorer.

Run with:
    pytest tests/test_explorer.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from explorer import (
    normalize_tag,
    normalize_manual_name,
    group_by_extension,
    find_multi_extension_instructions,
    cross_reference,
    build_shared_graph,
    load_instr_dict,
    scan_isa_manual,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_INSTR_DICT = {
    "add": {
        "encoding": "0000000----------000-----0110011",
        "variable_fields": ["rd", "rs1", "rs2"],
        "extension": ["rv_i"],
        "match": "0x33",
        "mask": "0xfe00707f",
    },
    "sh1add": {
        "encoding": "0010000----------010-----0110011",
        "variable_fields": ["rd", "rs1", "rs2"],
        "extension": ["rv_zba"],
        "match": "0x20002033",
        "mask": "0xfe00707f",
    },
    "aes32dsi": {
        "encoding": "00101------------000-----0110011",
        "variable_fields": ["rd", "rs1", "rs2", "bs"],
        "extension": ["rv32_zknd", "rv32_zk", "rv32_zkn"],
        "match": "0x28000033",
        "mask": "0x3e00707f",
    },
    "add_uw": {
        "encoding": "0000100----------000-----0111011",
        "variable_fields": ["rd", "rs1", "rs2"],
        "extension": ["rv64_zba"],
        "match": "0x800003b",
        "mask": "0xfe00707f",
    },
}

# ---------------------------------------------------------------------------
# Tier 1 — Normalisation
# ---------------------------------------------------------------------------

class TestNormalizeTag:
    def test_strips_rv_prefix(self):
        assert normalize_tag("rv_zba") == "zba"

    def test_strips_rv32_prefix(self):
        assert normalize_tag("rv32_zknd") == "zknd"

    def test_strips_rv64_prefix(self):
        assert normalize_tag("rv64_zba") == "zba"

    def test_lowercases_result(self):
        assert normalize_tag("rv_I") == "i"

    def test_no_prefix(self):
        # tags without a recognised prefix are just lowercased
        assert normalize_tag("M") == "m"

    def test_single_letter_base(self):
        assert normalize_tag("rv_i") == "i"
        assert normalize_tag("rv_m") == "m"


class TestNormalizeManualName:
    def test_lowercase(self):
        assert normalize_manual_name("Zba") == "zba"

    def test_already_lower(self):
        assert normalize_manual_name("zbb") == "zbb"

    def test_single_letter(self):
        assert normalize_manual_name("M") == "m"

    def test_sv_extension(self):
        assert normalize_manual_name("Sv39") == "sv39"

# ---------------------------------------------------------------------------
# Tier 1 — Grouping
# ---------------------------------------------------------------------------

class TestGroupByExtension:
    def test_basic_grouping(self):
        groups = group_by_extension(SAMPLE_INSTR_DICT)
        assert "rv_i" in groups
        assert "ADD" in groups["rv_i"]

    def test_multi_extension_instruction_appears_in_each_group(self):
        groups = group_by_extension(SAMPLE_INSTR_DICT)
        assert "AES32DSI" in groups["rv32_zknd"]
        assert "AES32DSI" in groups["rv32_zk"]
        assert "AES32DSI" in groups["rv32_zkn"]

    def test_mnemonic_uppercased(self):
        groups = group_by_extension(SAMPLE_INSTR_DICT)
        for mnemonics in groups.values():
            for m in mnemonics:
                assert m == m.upper(), f"{m} should be uppercase"

    def test_empty_dict(self):
        assert group_by_extension({}) == {}

    def test_correct_counts(self):
        groups = group_by_extension(SAMPLE_INSTR_DICT)
        # rv_i has only ADD
        assert len(groups["rv_i"]) == 1
        # rv_zba has SH1ADD; rv64_zba has ADD_UW
        assert len(groups["rv_zba"]) == 1
        assert len(groups["rv64_zba"]) == 1


class TestFindMultiExtensionInstructions:
    def test_finds_multi(self):
        multi = find_multi_extension_instructions(SAMPLE_INSTR_DICT)
        mnemonics = [m for m, _ in multi]
        assert "AES32DSI" in mnemonics

    def test_does_not_include_single(self):
        multi = find_multi_extension_instructions(SAMPLE_INSTR_DICT)
        mnemonics = [m for m, _ in multi]
        assert "ADD" not in mnemonics

    def test_sorted_alphabetically(self):
        multi = find_multi_extension_instructions(SAMPLE_INSTR_DICT)
        mnemonics = [m for m, _ in multi]
        assert mnemonics == sorted(mnemonics)

    def test_empty_dict(self):
        assert find_multi_extension_instructions({}) == []

    def test_all_extensions_present(self):
        multi = find_multi_extension_instructions(SAMPLE_INSTR_DICT)
        aes_entry = next(e for m, e in multi if m == "AES32DSI")
        assert set(aes_entry) == {"rv32_zknd", "rv32_zk", "rv32_zkn"}

# ---------------------------------------------------------------------------
# Tier 2 — Cross-Reference
# ---------------------------------------------------------------------------

class TestCrossReference:
    def test_matched(self):
        result = cross_reference({"zba", "m", "i"}, {"zba", "m", "f"})
        assert set(result["matched"]) == {"zba", "m"}

    def test_json_only(self):
        result = cross_reference({"zba", "i"}, {"zba", "f"})
        assert result["json_only"] == ["i"]

    def test_manual_only(self):
        result = cross_reference({"zba"}, {"zba", "f"})
        assert result["manual_only"] == ["f"]

    def test_no_overlap(self):
        result = cross_reference({"i", "m"}, {"f", "d"})
        assert result["matched"] == []
        assert set(result["json_only"]) == {"i", "m"}
        assert set(result["manual_only"]) == {"f", "d"}

    def test_complete_overlap(self):
        result = cross_reference({"i", "m"}, {"i", "m"})
        assert set(result["matched"]) == {"i", "m"}
        assert result["json_only"] == []
        assert result["manual_only"] == []

    def test_results_are_sorted(self):
        result = cross_reference({"zbb", "zba", "i"}, {"m", "f", "zba"})
        assert result["matched"] == sorted(result["matched"])
        assert result["json_only"] == sorted(result["json_only"])
        assert result["manual_only"] == sorted(result["manual_only"])

    def test_empty_inputs(self):
        result = cross_reference(set(), set())
        assert result == {"matched": [], "json_only": [], "manual_only": []}

# ---------------------------------------------------------------------------
# Tier 3 — Shared-Instruction Graph
# ---------------------------------------------------------------------------

class TestBuildSharedGraph:
    def test_shared_edge_present(self):
        graph = build_shared_graph(SAMPLE_INSTR_DICT)
        # aes32dsi appears in rv32_zknd, rv32_zk, rv32_zkn -> all three connected
        assert "rv32_zk" in graph["rv32_zknd"]
        assert "rv32_zkn" in graph["rv32_zknd"]

    def test_graph_is_symmetric(self):
        graph = build_shared_graph(SAMPLE_INSTR_DICT)
        for node, neighbours in graph.items():
            for n in neighbours:
                assert node in graph[n], f"Edge {node}<->{n} not symmetric"

    def test_no_self_loops(self):
        graph = build_shared_graph(SAMPLE_INSTR_DICT)
        for node, neighbours in graph.items():
            assert node not in neighbours

    def test_isolated_extensions_not_in_graph(self):
        graph = build_shared_graph(SAMPLE_INSTR_DICT)
        # rv_i and rv_zba each have a single-extension instruction
        assert "rv_i" not in graph
        assert "rv_zba" not in graph

    def test_empty_dict(self):
        assert build_shared_graph({}) == {}

# ---------------------------------------------------------------------------
# Integration — load real instr_dict.json if repos are present
# ---------------------------------------------------------------------------

LANDSCAPE_DIR = os.environ.get(
    "LANDSCAPE_DIR",
    os.path.join(os.path.dirname(__file__), "..", "riscv-extensions-landscape"),
)
MANUAL_DIR = os.environ.get(
    "MANUAL_DIR",
    os.path.join(os.path.dirname(__file__), "..", "riscv-isa-manual"),
)

REAL_INSTR_PATH = os.path.join(LANDSCAPE_DIR, "src", "instr_dict.json")
REAL_MANUAL_SRC = os.path.join(MANUAL_DIR, "src")


@pytest.mark.skipif(
    not os.path.exists(REAL_INSTR_PATH),
    reason="riscv-extensions-landscape repo not cloned",
)
class TestIntegrationInstrDict:
    def setup_method(self):
        self.instr_dict = load_instr_dict(REAL_INSTR_PATH)

    def test_loads_nonempty(self):
        assert len(self.instr_dict) > 0

    def test_every_entry_has_extension(self):
        for mnemonic, info in self.instr_dict.items():
            assert "extension" in info, f"{mnemonic} missing 'extension' field"
            assert isinstance(info["extension"], list)
            assert len(info["extension"]) >= 1

    def test_groups_nonempty(self):
        groups = group_by_extension(self.instr_dict)
        assert len(groups) > 0

    def test_normalize_produces_no_prefix(self):
        for info in self.instr_dict.values():
            for tag in info["extension"]:
                norm = normalize_tag(tag)
                assert not norm.startswith("rv"), f"Unexpected prefix in '{norm}'"


@pytest.mark.skipif(
    not os.path.exists(REAL_MANUAL_SRC),
    reason="riscv-isa-manual repo not cloned",
)
class TestIntegrationManualScan:
    def test_scan_returns_nonempty_set(self):
        names = scan_isa_manual(REAL_MANUAL_SRC)
        assert len(names) > 0

    def test_scan_finds_known_extensions(self):
        names = scan_isa_manual(REAL_MANUAL_SRC)
        # These are well-known extensions that must appear in the manual
        for expected in ["zba", "zbb", "m", "f", "d"]:
            assert expected in names, f"Expected '{expected}' in manual scan"
