#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys
from pathlib import Path

DEFAULT_TEX = "./papers/main.tex"
DEFAULT_BIB = "./papers/refs.bib"
DEFAULT_OUT = "./out"
DEFAULT_CONFIG = "./cite_guard/config.yaml"

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cite-guard",
        description=(
            "Multistage per-reference QA pipeline for AI/CS + policy papers.\n\n"
            "Defaults (repo root):\n"
            "  --tex ./papers/main.tex\n"
            "  --bib ./papers/refs.bib\n"
            "  --out ./out\n"
            "  --ml-profile neurips\n\n"
            "Run order (typical):\n"
            "  init -> audit -> resolve -> ground --fetch -> venue -> ml -> review_critiques\n\n"
            "Examples:\n"
            "  python3 cite-guard/scripts/citeguard_cli.py init\n"
            "  python3 cite-guard/scripts/citeguard_cli.py resolve --only \"(vaswani|lewis)\"\n"
            "  python3 cite-guard/scripts/citeguard_cli.py ground --fetch\n"
            "  python3 cite-guard/scripts/citeguard_cli.py review_critiques --rules-profile neurips\n"
            "  python3 cite-guard/scripts/citeguard_cli.py review_critiques --weights audit=1,resolve=2,ground=2,venue=1,ml=1\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--config", default=DEFAULT_CONFIG, help=f"Config YAML path (default: {DEFAULT_CONFIG})")
    p.add_argument("--tex", default=DEFAULT_TEX, help=f"Main TeX file (default: {DEFAULT_TEX})")
    p.add_argument("--bib", default=DEFAULT_BIB, help=f"BibTeX file (default: {DEFAULT_BIB})")
    p.add_argument("--out", default=DEFAULT_OUT, help=f"Output directory (default: {DEFAULT_OUT})")
    p.add_argument("--only", default=None, help="Optional regex to process only matching bib_key rows")
    p.add_argument("--venue-profile", default=None, help="policy_generic|jcp|ipr (overrides config)")
    p.add_argument("--ml-profile", default=None, help="neurips|icml|iclr|ml_generic (overrides config; default neurips)")
    p.add_argument("--rules-profile", default=None, help="Blocker rules profile name (default uses ml_profile; e.g., neurips)")
    p.add_argument("--fetch", action="store_true", help="Enable evidence fetching in ground stage (overrides config)")
    p.add_argument("--no-fetch", action="store_true", help="Disable evidence fetching in ground stage (overrides config)")
    p.add_argument("--weights", default=None, help="Override stage weights e.g. audit=1,resolve=2,ground=2,venue=1,ml=1")
    p.add_argument("--confidence-weighting", default=None, help="equal|linear|quadratic (overrides config)")

    sp = p.add_subparsers(dest="stage", required=True)
    sp.add_parser("init", help="Create out/audit_references.csv from the BibTeX file.")
    sp.add_parser("audit", help="Populate audit_* columns per reference.")
    sp.add_parser("resolve", help="Populate resolve_* columns per reference; write refs.corrected.bib.")
    sp.add_parser("ground", help="Populate ground_* columns per reference; write grounding report/rewrites.")
    sp.add_parser("venue", help="Populate venue_* columns per reference (policy lens).")
    sp.add_parser("ml", help="Populate ml_* columns per reference (ML lens; default NeurIPS).")
    sp.add_parser("review_critiques", help="Compute reference_quality_score and produce ranked critique outputs.")
    return p

def main() -> int:
    # ensure local scripts importable
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    args = build_parser().parse_args()
    tex_path = Path(args.tex)
    bib_path = Path(args.bib)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.stage == "init":
        from citeguard_stage_init import run_init
        return run_init(tex_path, bib_path, out_dir, args)
    if args.stage == "audit":
        from citeguard_stage_audit import run_audit
        return run_audit(tex_path, bib_path, out_dir, args)
    if args.stage == "resolve":
        from citeguard_stage_resolve import run_resolve
        return run_resolve(tex_path, bib_path, out_dir, args)
    if args.stage == "ground":
        from citeguard_stage_ground import run_ground
        return run_ground(tex_path, bib_path, out_dir, args)
    if args.stage == "venue":
        from citeguard_stage_venue import run_venue
        return run_venue(tex_path, bib_path, out_dir, args)
    if args.stage == "ml":
        from citeguard_stage_ml import run_ml
        return run_ml(tex_path, bib_path, out_dir, args)
    if args.stage == "review_critiques":
        from citeguard_stage_review_critiques import run_review_critiques
        return run_review_critiques(tex_path, bib_path, out_dir, args)

    raise RuntimeError(f"Unknown stage: {args.stage}")

if __name__ == "__main__":
    raise SystemExit(main())
