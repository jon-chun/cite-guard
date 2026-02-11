---
name: cite-guard-review-critiques
description: >
  Final stage: compute reference_quality_score by weighted QUALITY×CONFIDENCE across audit/resolve/ground/venue/ml; rank and assign review_priority; includes default + venue-specific blocker rules.
license: MIT
metadata:
  version: 1.0.0
  category: research-qa
  tags: [ranking, blocker, review]
---

# cite-guard-review-critiques

Computes per reference:
- reference_quality_score [0-100]
- review_priority: low|medium|high|blocker

Blocker rules:
- default: unresolved/low-confidence resolution
- plus venue-specific (e.g., neurips) rules configurable in config.yaml or via CLI profile.

Outputs:
- out/review_critiques.csv
- out/review_critiques.md
