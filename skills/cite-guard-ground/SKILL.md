---
name: cite-guard-ground
description: >
  Stage ground: evaluates whether each reference supports the claims it is cited for; fetches evidence preferring md/html/tex/rtf/txt/pdf; writes ground_* columns and produces grounding reports.
license: MIT
metadata:
  version: 1.0.0
  category: research-qa
  tags: [grounding, claims, evidence]
---

# cite-guard-ground

Extracts atomic claim-sentences from TeX, maps cited keys, then for each reference:
- fetches best available evidence (md > html > tex > rtf > txt > pdf)
- selects snippets with keyword overlap
- computes a heuristic support score (supported/weak/unsupported/contradicted)
- emits safe LaTeX rewrite suggestions for high-priority unsupported claims

Per reference outputs:
- ground_quality [0-100]
- ground_confidence [0-100]
- ground_remediation

Artifacts:
- out/claims.json
- out/grounding_report.md
- out/rewrites.tex
- out/evidence_cache/

Run: `/cite_guard_ground` or `python3 ... ground --fetch`
