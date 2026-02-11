---
name: cite-guard-resolve
description: >
  Stage resolve: resolve each reference against OpenAlex/Crossref/arXiv/DBLP; detect hallucinations and metadata mismatches; writes resolve_* columns and refs.corrected.bib.
license: MIT
metadata:
  version: 1.0.0
  category: research-qa
  tags: [openalex, crossref, arxiv, dblp, doi, resolution]
---

# cite-guard-resolve

Deterministically resolves references:
1) DOI exact (Crossref/OpenAlex)
2) arXiv exact
3) Fuzzy title+author (OpenAlex → Crossref fallback → DBLP tie-break)

Per reference outputs:
- resolve_quality [0-100]
- resolve_confidence [0-100]
- resolve_remediation

Also:
- out/resolution_cache.json
- out/refs.corrected.bib (resolved entries canonicalized)
- out/stage_resolve_report.md

Run: `/cite_guard_resolve` or `python3 ... resolve`
