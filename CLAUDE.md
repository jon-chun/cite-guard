# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Cite-Guard?

A hallucination-resistant citation and claim-grounding pipeline for LaTeX/BibTeX papers (AI/CS + governance/policy). It runs six sequential stages against a paper's references, producing a per-reference audit CSV with quality scores, stage reports, and a ranked list of problematic references with configurable blocker rules (e.g., NeurIPS profile).

## Running the Pipeline

```bash
# Install optional deps (graceful degradation without them)
python -m pip install --upgrade requests beautifulsoup4 feedparser PyPDF2

# Full pipeline run (stages must run in order)
python3 cite_guard/cli.py init
python3 cite_guard/cli.py audit
python3 cite_guard/cli.py resolve
python3 cite_guard/cli.py ground --fetch
python3 cite_guard/cli.py venue
python3 cite_guard/cli.py ml --ml-profile neurips
python3 cite_guard/cli.py review_critiques --rules-profile neurips

# Process subset of references
python3 cite_guard/cli.py resolve --only "(vaswani|lewis)"

# Override paths
python3 cite_guard/cli.py init --tex ./papers/main.tex --bib ./papers/refs.bib --out ./out
```

Default paths: `--tex ./papers/main.tex`, `--bib ./papers/refs.bib`, `--out ./out`.

There is no test suite or build system. This is a pure Python 3.10+ CLI with no packaging config.

## Architecture

### Pipeline Flow

Each stage reads/updates a shared CSV (`out/audit_references.csv`) with per-reference rows. Stages populate `{stage}_quality`, `{stage}_confidence`, and `{stage}_remediation` columns for their stage. The five scored stages are: `audit`, `resolve`, `ground`, `venue`, `ml`. The `review_critiques` stage computes the final `reference_quality_score` as a confidence-weighted mean and applies blocker rules.

### Module Responsibilities

- **`cli.py`** — Argument parser and stage dispatcher. Imports stages lazily via relative imports (adds its own parent dir to `sys.path`).
- **`citeguard_csv.py`** — Central CSV read/write layer. Defines `required_columns()` and provides `load_rows`, `filter_rows`, `update_row`, `write_rows_atomic` (atomic write via tmp+rename).
- **`citeguard_bib_parse.py`** — Custom BibTeX parser (no external deps). Returns `BibEntry` dataclasses with key, entry_type, raw text, and parsed fields dict.
- **`citeguard_tex_parse.py`** — LaTeX parser: expands `\input/\include`, extracts citation uses (`\cite`, `\citet`, `\citep`, etc.), tracks sections and abstract/conclusion context. Returns `CitationUse` and `Span` dataclasses.
- **`citeguard_claims.py`** — Extracts `Claim` dataclasses from citation uses. Classifies priority (high for abstract/conclusion), SOTA detection, and claim strength.
- **`citeguard_similarity.py`** — Token-level similarity: `jaccard()` for title matching, `author_overlap()` for author last-name overlap. Used by resolve and ground stages.
- **`citeguard_resolve_backends.py`** — External API clients for OpenAlex, Crossref, arXiv (via feedparser), and DBLP. Each returns `Candidate` dataclasses with match confidence and canonical metadata.
- **`citeguard_evidence.py`** — HTTP fetcher and text extractor for evidence artifacts. Supports md/html/tex/rtf/txt/pdf formats. Optional deps: `requests`, `beautifulsoup4`, `PyPDF2`.
- **`citeguard_yaml.py`** — Minimal custom YAML parser (no PyYAML dep). Only supports the subset used by `config.yaml`.

### Key Design Patterns

- **No external build/package deps required** — All parsers (BibTeX, TeX, YAML) are hand-rolled to keep the tool dependency-light. Optional deps (`requests`, `beautifulsoup4`, `feedparser`, `PyPDF2`) are imported with try/except and degrade gracefully.
- **Shared mutable state via CSV** — All stages read and write to the same `audit_references.csv`. The `resolution_cache.json` carries cross-stage signals (mismatch flags, ground signals) used by later stages.
- **Stages use relative imports** — `cli.py` adds its parent directory to `sys.path`, so stage modules import each other by bare name (e.g., `from citeguard_csv import load_rows`), not package-qualified imports.
- **Blocker rules are config-driven** — Default blockers plus per-profile blockers (e.g., NeurIPS) are defined in `config.yaml` under `review.default_blockers` and `review.profiles.<name>.blockers`. The blocker functions live in `citeguard_stage_review_critiques.py`.

### Configuration

All tunable parameters live in `cite_guard/config.yaml`: stage weights, confidence weighting mode, audit penalties, resolve thresholds, grounding thresholds (SOTA keywords, negation tokens, support thresholds), and blocker rule definitions.

## Claude Code Plugin

This repo is also a Claude Code plugin (`.claude-plugin/plugin.json`). The `commands/` directory contains slash-command wrappers and `skills/` contains `SKILL.md` files that invoke the same Python CLI stages.
