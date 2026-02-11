---
name: cite-guard-audit
description: >
  Stage audit: bibliography hygiene checks per reference and writes audit_quality/audit_confidence/audit_remediation per row.
license: MIT
metadata:
  version: 1.0.0
  category: research-qa
  tags: [bibtex, hygiene, qa]
---

# cite-guard-audit

Scores BibTeX integrity (not truth):
- missing core fields, malformed entries, unused refs, placeholder values.

Per reference outputs:
- audit_quality [0-100]
- audit_confidence [0-100]
- audit_remediation: one-sentence fix plan

Run: `/cite_guard_audit` or `python3 ... audit`

Stop if init CSV missing.
