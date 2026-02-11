# Cite-Guard

**Cite-Guard** is a *hallucination-resistant* citation and claim-grounding pipeline for LaTeX/BibTeX papers (AI/CS + governance/policy). It produces a per-reference audit table (`out/audit_references.csv`), stage reports, and a ranked list of problematic references with **configurable default + venue-specific blocker rules** (e.g., NeurIPS).

![Cite-Guard logo](assets/logo.svg)

## Features

Cite-Guard runs **five per-reference stages** plus a final ranking stage:

1. **audit** — BibTeX hygiene (missing fields, placeholders, unused refs)
2. **resolve** — Canonical resolution via **OpenAlex / Crossref / arXiv / DBLP**, mismatch detection, and `refs.corrected.bib`
3. **ground** — Claim ↔ citation grounding using fetched evidence (prefers `md > html > tex > rtf > txt > pdf`), plus rewrite suggestions
4. **venue** — Policy/governance lens: source authority and genre appropriateness
5. **ml** — ML venue lens (default **NeurIPS**): canonicality, baseline relevance, recency / SOTA usage
6. **review_critiques** — Computes `reference_quality_score`, ranks references, and applies blocker rules

## Repository layout

```text
cite-guard/
  .claude-plugin/           # Claude Code plugin manifest
  commands/                 # Slash-command wrappers for Claude Code
  skills/                   # Claude Skills (SKILL.md)
  cite_guard/               # Python implementation (CLI + stages)
  assets/logo.svg           # Vector logo (SVG)
  README.md
```

## Requirements

- Python 3.10+

Recommended dependencies (strongly suggested for best results):

```bash
python -m pip install --upgrade requests beautifulsoup4 feedparser PyPDF2
```

If optional deps are missing, Cite-Guard degrades gracefully (lower confidence and less evidence retrieval/extraction).

## Defaults (repo root)

By default, Cite-Guard expects:

- TeX: `./papers/main.tex`
- BibTeX: `./papers/refs.bib`
- Outputs: `./out/`

Override with CLI flags `--tex`, `--bib`, `--out`.

## Quickstart (CLI)

From your repo root:

```bash
python3 cite_guard/cli.py init
python3 cite_guard/cli.py audit
python3 cite_guard/cli.py resolve
python3 cite_guard/cli.py ground --fetch
python3 cite_guard/cli.py venue
python3 cite_guard/cli.py ml --ml-profile neurips
python3 cite_guard/cli.py review_critiques --rules-profile neurips
```

### What you get after a full run

In `./out/`:

- `audit_references.csv` — **main per-reference table**
- `stage_audit_report.md`
- `resolution_cache.json`
- `stage_resolve_report.md`
- `refs.corrected.bib`
- `claims.json`
- `grounding_report.md`
- `rewrites.tex`
- `evidence_index.json` + `evidence_cache/<bib_key>/...`
- `venue_report.md`
- `ml_report.md`
- `review_critiques.csv` + `review_critiques.md`

## Using with Claude Code CLI

1. Copy the `cite-guard/` folder into the repo root of your paper project.
2. Launch Claude Code in that repo.
3. Use the slash commands (they invoke the same Python CLI):

- `/cite_guard_help`
- `/cite_guard_init`
- `/cite_guard_audit`
- `/cite_guard_resolve`
- `/cite_guard_ground --fetch`
- `/cite_guard_venue`
- `/cite_guard_ml --ml-profile neurips`
- `/cite_guard_review_critiques --rules-profile neurips`

## Configuration

Edit:

- `cite_guard/config.yaml`

Key settings:

- `paper_tex`, `bib_file`, `out_dir`
- `ml_profile` (default: **neurips**)
- `venue_profile` (policy_generic / jcp / ipr)
- `evidence_preference` (default: `["md","html","htm","tex","rtf","txt","pdf"]`)
- `ground_fetch_enabled` (true/false)
- `weights` and `confidence_weighting` for final scoring
- `review.default_blockers` and `review.profiles.<profile>.blockers`

## Scoring

For each stage `i ∈ {audit, resolve, ground, venue, ml}`:

- stage contribution = `QUALITY_i × f(CONFIDENCE_i)`

Default confidence function:

- `linear`: `f(c) = c/100` (also supports `equal`, `quadratic`)

Final score:

- `reference_quality_score = weighted_mean(stage_contributions)`

Override weights:

```bash
python3 cite_guard/cli.py review_critiques --weights audit=1,resolve=2,ground=2,venue=1,ml=1
```

## Blocker rules (general + profile-specific)

Cite-Guard supports:

- **default blockers** (general-purpose)
- **profile-specific blockers** via `--rules-profile` (or by default derived from `--ml-profile`)

### Default blocker (general)

- `resolve_unresolved_or_low_confidence`  
  Triggers if `resolve_quality < 40` OR `resolve_confidence < 50`.

### NeurIPS profile blockers

Enabled by default when `ml_profile: neurips` (or `--rules-profile neurips`):

1. `high_priority_claim_unsupported`  
   Any **abstract or conclusion** claim citing this reference is unsupported/contradicted.

2. `sota_claim_with_unresolved_or_low_conf_ref`  
   Any SOTA-like claim is weakly supported **and** the reference resolution is not strong.

3. `year_or_venue_mismatch_after_resolve`  
   Year or venue mismatch flagged after canonical resolution.

Edit in `cite_guard/config.yaml`:

```yaml
review:
  default_blockers:
    - "resolve_unresolved_or_low_confidence"
  profiles:
    neurips:
      blockers:
        - "high_priority_claim_unsupported"
        - "sota_claim_with_unresolved_or_low_conf_ref"
        - "year_or_venue_mismatch_after_resolve"
```

## Advanced usage

### Process only a subset of references

```bash
python3 cite_guard/cli.py resolve --only "(vaswani|lewis|brown)"
```

### Run offline (no evidence fetching)

```bash
python3 cite_guard/cli.py ground --no-fetch
```

## Notes / limitations

- TeX parsing is lightweight (expands `\input/\include`, extracts cite commands).
- Grounding is a fast heuristic (token overlap + negation). It’s designed to be dependency-light.
  You can later replace the grounding scorer with NLI or retrieval+reranking.

## License

MIT
