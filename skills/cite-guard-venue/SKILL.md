---
name: cite-guard-venue
description: >
  Stage venue: policy venue lens (governance/ethics/policy) scoring per reference based on authority/genre appropriateness for policy claims; writes venue_* columns.
license: MIT
metadata:
  version: 1.0.0
  category: research-qa
  tags: [policy, governance, ethics]
---

# cite-guard-venue

Per reference:
- classifies genre (peer-reviewed/preprint/report/standard/blog)
- uses claim context (if available) to penalize weak authority for normative/policy claims
- outputs venue_quality/confidence/remediation

Supports venue-specific profiles; default policy_generic.
