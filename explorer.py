"""
RISC-V Instruction Set Explorer
Coding challenge for the RISC-V Extensions Landscape mentorship.

Tiers:
  1 - Parse instr_dict.json, group by extension, find multi-extension instructions
  2 - Cross-reference extensions against the official ISA manual AsciiDoc sources
  3 - Unit tests (tests/test_explorer.py), README, shared-instruction graph
"""

import json
import os
import re
import sys
import subprocess
from pathlib import Path
from collections import defaultdict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LANDSCAPE_REPO = "https://github.com/rpsene/riscv-extensions-landscape.git"
MANUAL_REPO    = "https://github.com/riscv/riscv-isa-manual.git"

# Regex to detect extension names inside AsciiDoc prose.
# Matches:
#   Z-extensions  : Zba, Zbb, Zicsr, Zifencei, Zbkb, ...
#   S-extensions  : Sv39, Sv48, Svinval, ...
#   Single-letter : I M A F D Q C H V  (base ISA letters used as extension names)
_EXT_PATTERN = re.compile(
    r'\b(Z[a-z][a-z0-9]*|S[uv][a-z0-9]+|[IMAFDC])\b'
)

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def normalize_tag(tag: str) -> str:
    """
    Convert an instr_dict.json extension tag to a canonical lowercase key.

    Examples
    --------
    rv_zba   -> zba
    rv64_zba -> zba
    rv32_m   -> m
    rv_i     -> i
    """
    t = tag.lower()
    t = re.sub(r'^rv(32|64)?_', '', t)
    return t


def normalize_manual_name(name: str) -> str:
    """
    Convert an extension name found in AsciiDoc prose to the same canonical form.

    Examples
    --------
    Zba  -> zba
    M    -> m
    Sv39 -> sv39
    """
    return name.lower()

# ---------------------------------------------------------------------------
# Tier 1 — Instruction Set Parsing
# ---------------------------------------------------------------------------

def load_instr_dict(path: str) -> dict:
    """Load and return the raw instr_dict.json as a dict."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def group_by_extension(instr_dict: dict) -> dict:
    """
    Return a mapping of extension tag -> list of mnemonic strings.

    The key is the raw tag from the JSON (e.g. 'rv_zba'), not normalised,
    so callers can display the original names in the summary table.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for mnemonic, info in instr_dict.items():
        for ext in info.get("extension", []):
            groups[ext].append(mnemonic.upper())
    return dict(groups)


def find_multi_extension_instructions(instr_dict: dict) -> list[tuple]:
    """
    Return a list of (mnemonic, [extensions]) for instructions that appear
    in more than one extension.
    """
    results = []
    for mnemonic, info in instr_dict.items():
        exts = info.get("extension", [])
        if len(exts) > 1:
            results.append((mnemonic.upper(), exts))
    return sorted(results, key=lambda x: x[0])


def print_tier1(instr_dict: dict) -> None:
    groups = group_by_extension(instr_dict)
    multi  = find_multi_extension_instructions(instr_dict)

    # --- Summary table ---
    print("\n" + "=" * 60)
    print("TIER 1 — Extension Summary Table")
    print("=" * 60)
    col_w = max(len(tag) for tag in groups) + 2
    header = f"{'Extension':<{col_w}} | {'Count':^13} | Example Mnemonic"
    print(header)
    print("-" * len(header))
    for tag in sorted(groups):
        mnemonics = groups[tag]
        count     = len(mnemonics)
        example   = mnemonics[0]
        count_str = f"{count} instruction{'s' if count != 1 else ''}"
        print(f"{tag:<{col_w}} | {count_str:^13} | e.g. {example}")

    # --- Multi-extension instructions ---
    print(f"\n{'=' * 60}")
    print(f"TIER 1 — Multi-Extension Instructions ({len(multi)} found)")
    print("=" * 60)
    if not multi:
        print("  (none)")
    for mnemonic, exts in multi:
        print(f"  {mnemonic:<20}  {', '.join(exts)}")

# ---------------------------------------------------------------------------
# Tier 2 — Cross-Reference with the ISA Manual
# ---------------------------------------------------------------------------

def scan_isa_manual(manual_src_dir: str) -> set[str]:
    """
    Walk all .adoc files under manual_src_dir and return the set of
    normalised extension names found in the prose.
    """
    src_path = Path(manual_src_dir)
    if not src_path.exists():
        raise FileNotFoundError(f"Manual src directory not found: {manual_src_dir}")

    found: set[str] = set()
    for adoc_file in src_path.rglob("*.adoc"):
        text = adoc_file.read_text(encoding="utf-8", errors="replace")
        for match in _EXT_PATTERN.finditer(text):
            found.add(normalize_manual_name(match.group(1)))
    return found


def cross_reference(json_tags: set[str], manual_names: set[str]) -> dict:
    """
    Compare the normalised extension sets from both sources and return a
    dict with keys: matched, json_only, manual_only.
    """
    matched    = json_tags & manual_names
    json_only  = json_tags - manual_names
    manual_only = manual_names - json_tags
    return {
        "matched":     sorted(matched),
        "json_only":   sorted(json_only),
        "manual_only": sorted(manual_only),
    }


def print_tier2(instr_dict: dict, manual_src_dir: str) -> None:
    # Collect normalised extension names from instr_dict
    raw_tags   = set()
    for info in instr_dict.values():
        for ext in info.get("extension", []):
            raw_tags.add(ext)
    json_norm  = {normalize_tag(t) for t in raw_tags}

    print("\n" + "=" * 60)
    print("TIER 2 — Scanning ISA Manual AsciiDoc files …")
    print("=" * 60)
    manual_names = scan_isa_manual(manual_src_dir)
    result       = cross_reference(json_norm, manual_names)

    matched     = result["matched"]
    json_only   = result["json_only"]
    manual_only = result["manual_only"]

    print(f"\nCount summary: {len(matched)} matched | "
          f"{len(json_only)} in JSON only | "
          f"{len(manual_only)} in manual only\n")

    print(f"--- Extensions in instr_dict.json but NOT in ISA manual "
          f"({len(json_only)}) ---")
    for name in json_only:
        print(f"  {name}")

    print(f"\n--- Extensions in ISA manual but NOT in instr_dict.json "
          f"({len(manual_only)}) ---")
    for name in manual_only:
        print(f"  {name}")

    print(f"\n--- Matched ({len(matched)}) ---")
    for name in matched:
        print(f"  {name}")

# ---------------------------------------------------------------------------
# Tier 3 — Shared-Instruction Graph
# ---------------------------------------------------------------------------

def build_shared_graph(instr_dict: dict) -> dict:
    """
    Return an adjacency dict: extension -> set of extensions that share
    at least one instruction with it.  Keys are raw tags from the JSON.
    """
    adjacency: dict[str, set[str]] = defaultdict(set)
    for info in instr_dict.values():
        exts = info.get("extension", [])
        if len(exts) > 1:
            for i, a in enumerate(exts):
                for b in exts[i + 1:]:
                    adjacency[a].add(b)
                    adjacency[b].add(a)
    return dict(adjacency)


def print_tier3_graph(instr_dict: dict) -> None:
    graph = build_shared_graph(instr_dict)

    print("\n" + "=" * 60)
    print("TIER 3 — Shared-Instruction Graph")
    print("(extensions connected by ── share at least one instruction)")
    print("=" * 60)

    if not graph:
        print("  No shared instructions found.")
        return

    printed: set[frozenset] = set()
    for ext in sorted(graph):
        for neighbour in sorted(graph[ext]):
            edge = frozenset([ext, neighbour])
            if edge not in printed:
                print(f"  {ext}  ──  {neighbour}")
                printed.add(edge)

# ---------------------------------------------------------------------------
# Repository helpers
# ---------------------------------------------------------------------------

def clone_if_missing(url: str, dest: str) -> None:
    """Shallow-clone a repo if the destination directory does not exist."""
    if not os.path.exists(dest):
        print(f"Cloning {url} …")
        subprocess.run(
            ["git", "clone", "--depth=1", url, dest],
            check=True,
            capture_output=True,
        )

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Allow overriding repo paths via environment variables so the script
    # also works when the repos are already cloned locally.
    landscape_dir = os.environ.get(
        "LANDSCAPE_DIR",
        os.path.join(os.path.dirname(__file__), "riscv-extensions-landscape"),
    )
    manual_dir = os.environ.get(
        "MANUAL_DIR",
        os.path.join(os.path.dirname(__file__), "riscv-isa-manual"),
    )

    clone_if_missing(LANDSCAPE_REPO, landscape_dir)
    clone_if_missing(MANUAL_REPO,    manual_dir)

    instr_dict_path = os.path.join(landscape_dir, "src", "instr_dict.json")
    manual_src_dir  = os.path.join(manual_dir, "src")

    instr_dict = load_instr_dict(instr_dict_path)

    print_tier1(instr_dict)
    print_tier2(instr_dict, manual_src_dir)
    print_tier3_graph(instr_dict)


if __name__ == "__main__":
    main()
