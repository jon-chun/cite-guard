from __future__ import annotations
import csv, re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

STAGES = ["audit", "resolve", "ground", "venue", "ml"]
IDENTITY_COLS = ["bib_key", "bib_source_file", "bib_entry_type", "bib_raw"]
FINAL_COLS = ["reference_quality_score", "reference_quality_notes", "review_priority"]

def required_columns() -> List[str]:
    cols = IDENTITY_COLS[:]
    for st in STAGES:
        cols += [f"{st}_quality", f"{st}_confidence", f"{st}_remediation"]
    cols += FINAL_COLS
    return cols

def load_rows(csv_path: Path) -> Tuple[List[Dict[str,str]], List[str]]:
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        fieldnames = r.fieldnames or []
        rows = list(r)
    return rows, fieldnames

def write_rows_atomic(csv_path: Path, rows: List[Dict[str,str]], fieldnames: List[str]) -> None:
    tmp = csv_path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(csv_path)

def filter_rows(rows: List[Dict[str,str]], only_regex: Optional[str]) -> List[Dict[str,str]]:
    if not only_regex:
        return rows
    rx = re.compile(only_regex)
    return [r for r in rows if rx.search(r.get("bib_key",""))]

def update_row(rows: List[Dict[str,str]], bib_key: str, updates: Dict[str,str]) -> None:
    for r in rows:
        if r.get("bib_key") == bib_key:
            for k,v in updates.items():
                r[k]=str(v)
            return
    raise KeyError(f"bib_key not found: {bib_key}")
