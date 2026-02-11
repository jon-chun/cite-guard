---
name: cite-guard-ml
description: >
  Stage ml: ML venue lens (default NeurIPS) scoring per reference for technical fit: canonicality, baseline relevance, recency for SOTA claims; writes ml_* columns.
license: MIT
metadata:
  version: 1.0.0
  category: research-qa
  tags: [ml, neurips, icml, iclr]
---

# cite-guard-ml

Per reference:
- penalizes non-canonical versions for core method/baseline claims
- penalizes outdated citations used as SOTA
- outputs ml_quality/confidence/remediation

Default profile: neurips (override via CLI).
