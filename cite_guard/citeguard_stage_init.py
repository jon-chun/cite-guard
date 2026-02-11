from __future__ import annotations
from pathlib import Path
import json
from datetime import datetime, timezone
from citeguard_csv import required_columns, write_rows_atomic
from citeguard_bib_parse import parse_bib_file

STAGES = ["audit","resolve","ground","venue","ml"]

def run_init(tex_path: Path, bib_path: Path, out_dir: Path, args) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = parse_bib_file(bib_path)
    if not entries:
        raise SystemExit("No BibTeX entries found in bib file.")

    cols = required_columns()
    rows=[]
    for e in entries:
        row = {c:"" for c in cols}
        row["bib_key"]=e.key
        row["bib_source_file"]=str(bib_path)
        row["bib_entry_type"]=e.entry_type
        row["bib_raw"]=e.raw[:8000]  # cap
        for st in STAGES:
            row[f"{st}_quality"]="0"
            row[f"{st}_confidence"]="0"
            row[f"{st}_remediation"]="TBD"
        row["reference_quality_score"]=""
        row["reference_quality_notes"]=""
        row["review_priority"]=""
        rows.append(row)

    csv_path = out_dir/"audit_references.csv"
    write_rows_atomic(csv_path, rows, cols)

    meta = {
        "pipeline_version":"1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "tex": str(tex_path),
        "bib": str(bib_path),
        "out": str(out_dir),
        "args": vars(args),
    }
    (out_dir/"citeguard_run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[init] wrote {csv_path} with {len(rows)} references")
    return 0
