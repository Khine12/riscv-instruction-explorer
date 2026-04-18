# RISC-V Instruction Set Explorer

Coding challenge submission for the **Mapping the RISC-V Extensions Landscape** mentorship (LFX / RISC-V International, Summer 2026).

---

## What it does

| Tier | Description |
|------|-------------|
| 1 | Parses `instr_dict.json`, groups instructions by extension, prints a summary table, and identifies instructions that belong to more than one extension |
| 2 | Scans the official RISC-V ISA manual AsciiDoc sources and cross-references the extensions found there against those in `instr_dict.json` |
| 3 | Unit tests (38 tests, 100% passing), this README, and a text-based shared-instruction graph |

---

## Requirements

- Python 3.10+
- Git (to clone the data repositories on first run)
- `pytest` (for tests only)

---

## Install and run

```bash
# 1. Clone this repo
git clone <your-repo-url>
cd riscv-explorer

# 2. Install test dependency
pip install pytest

# 3. Run the explorer
#    On first run it will clone the two data repositories automatically.
python3 explorer.py
```

The script clones:
- `https://github.com/rpsene/riscv-extensions-landscape` (for `instr_dict.json`)
- `https://github.com/riscv/riscv-isa-manual` (for the AsciiDoc sources)

If you already have them cloned, point to them via environment variables to skip re-cloning:

```bash
LANDSCAPE_DIR=/path/to/riscv-extensions-landscape \
MANUAL_DIR=/path/to/riscv-isa-manual \
python3 explorer.py
```

---

## Run tests

```bash
pytest tests/test_explorer.py -v
```

Tests are split into:
- **Unit tests** — run on an embedded sample fixture, no network required
- **Integration tests** — run against the real repos; skipped automatically if repos are not present

---

## Sample output

```
============================================================
TIER 1 — Extension Summary Table
============================================================
Extension          Count  Example Mnemonic
------------------------------------------
rv32_c                 1  e.g. C_JAL
rv32_zk               10  e.g. AES32DSI
rv64_a                11  e.g. AMOADD_D
rv_i                  37  e.g. ADD
rv_v                 627  e.g. VAADD_VV
rv_zba                 3  e.g. SH1ADD
...

============================================================
TIER 1 — Multi-Extension Instructions (73 found)
============================================================
  ANDN                  rv_zbb, rv_zkn, rv_zks, rv_zk, rv_zbkb
  CLMUL                 rv_zbc, rv_zkn, rv_zks, rv_zk, rv_zbkc
  SHA256SIG0            rv_zknh, rv_zkn, rv_zk
  XPERM4                rv_zbkx, rv_zkn, rv_zks, rv_zk
...

============================================================
TIER 2 — Scanning ISA Manual AsciiDoc files
============================================================

Count summary: 51 matched | 34 in JSON only | 118 in manual only

--- Extensions in instr_dict.json but NOT in ISA manual (34) ---
  c_d
  d_zfa
  h
  v
  zvzip
  ...

--- Extensions in ISA manual but NOT in instr_dict.json (118) ---
  sv39
  svnapot
  zmmul
  zve32x
  ...

============================================================
TIER 3 — Shared-Instruction Graph
(extensions connected by ── share at least one instruction)
============================================================
  rv32_zk  ──  rv32_zkn
  rv32_zk  ──  rv32_zknd
  rv_zbb   ──  rv_zbkb
  rv_zbb   ──  rv_zk
  rv_zvbb  ──  rv_zvkn
  ...
```

---

## Design decisions

### Normalisation strategy

`instr_dict.json` uses prefixed tags like `rv_zba`, `rv64_zba`, and `rv32_zknd`. The ISA manual uses shorthand names like `Zba`, `M`, and `Sv39`. To compare them, both sides are normalised to a canonical lowercase key:

```
rv_zba    →  zba
rv64_zba  →  zba     # 32/64 bit qualifier stripped
rv32_zknd →  zknd
Zba       →  zba
M         →  m
Sv39      →  sv39
```

The normalisation intentionally strips the `rv32_` / `rv64_` qualifier. This means `rv64_zba` and `rv_zba` both map to `zba`, which is the correct behaviour: they are the same extension applied to different base ISAs, not two distinct extensions.

### Extension detection in AsciiDoc prose

The regex used to find extension names in the manual source files is:

```
\b(Z[a-z][a-z0-9]*|S[uv][a-z0-9]+|[IMAFDC])\b
```

This matches:
- Z-extensions: `Zba`, `Zbb`, `Zicsr`, `Zbkb`, …
- S-extensions: `Sv39`, `Svinval`, `Svnapot`, `Supm`, …
- Single-letter base ISA names: `I`, `M`, `A`, `F`, `D`, `C`

**Known limitation — false positives:** The `S[uv]` pattern also matches common English words that begin with "Su" or "Sv" (e.g. "Subject", "Subset", "Such"). These appear in the "manual only" list and inflate the count. A more precise approach would require either a curated allowlist of known extension names or more context-aware parsing of the AsciiDoc structure (e.g. only scanning within specific section headings or inline code spans). For this challenge the regex approach is used and the limitation is documented here.

**Known limitation — compound tags:** Tags like `rv_c_d` (C extension with D float support) and `rv_d_zfa` (D + Zfa) do not have a clean single-name equivalent in the manual. After normalisation they become `c_d` and `d_zfa`, which correctly appear in the "JSON only" list since the manual refers to these combinations inline in prose rather than by a dedicated tag.

### Graph representation

Extensions are connected in the graph when they share at least one instruction mnemonic. The graph is represented as a sorted edge list (text-based) rather than a rendered image, making it grep-able and diff-able. The edge list is deduplicated so each pair appears exactly once.

---

## Project structure

```
riscv-explorer/
├── explorer.py              # Main script — all three tiers
├── tests/
│   └── test_explorer.py     # 38 pytest unit + integration tests
├── requirements.txt
└── README.md
```
