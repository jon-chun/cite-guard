---
name: cite-guard-init
description: >
  Initialize the reference QA pipeline by creating out/audit_references.csv with one row per BibTeX entry and required stage columns.
license: MIT
metadata:
  version: 1.0.0
  category: research-qa
  tags: [bibtex, latex, citations, qa]
---

# cite-guard-init

Creates `out/audit_references.csv` with one row per BibTeX entry and columns:
- Identity: bib_key, bib_source_file, bib_entry_type, bib_raw
- Stage groups (audit/resolve/ground/venue/ml): `<stage>_{quality,confidence,remediation}`
- Final: reference_quality_score, reference_quality_notes, review_priority

Defaults (repo root):
- TeX: `./papers/main.tex`
- Bib: `./papers/refs.bib`
- Out: `./out`

Run via: `/cite_guard_init` or `python3 cite-guard/scripts/cite_guard_cli.py init`

Stop conditions: bib missing or zero entries; cannot write out.
