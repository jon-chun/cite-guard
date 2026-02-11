from __future__ import annotations
from pathlib import Path
import json, re
from citeguard_csv import load_rows, filter_rows, update_row, write_rows_atomic
from citeguard_yaml import load_yaml
from citeguard_bib_parse import parse_bib_file

TOP_ML_VENUES = ["neurips","icml","iclr","aaai","aistats","colt","acl","emnlp","naacl"]

def _is_canonical(venue: str) -> bool:
    v=(venue or "").lower()
    return any(x in v for x in TOP_ML_VENUES)

def run_ml(tex_path: Path, bib_path: Path, out_dir: Path, args) -> int:
    cfg={}
    cfg_path=Path(args.config)
    if cfg_path.exists():
        cfg=load_yaml(cfg_path.read_text(encoding="utf-8"))
    profile = (args.ml_profile or cfg.get("ml_profile") or "neurips").lower()

    csv_path=out_dir/"audit_references.csv"
    rows, cols = load_rows(csv_path)
    target_rows = filter_rows(rows, args.only)

    entries = {e.key: e for e in parse_bib_file(bib_path)}
    res_cache_path = out_dir/"resolution_cache.json"
    res_cache={}
    if res_cache_path.exists():
        try:
            res_cache=json.loads(res_cache_path.read_text(encoding="utf-8"))
        except Exception:
            res_cache={}

    report=["# ml_report\n\n"]

    for r in target_rows:
        key=r["bib_key"]
        e=entries.get(key)
        if not e:
            update_row(rows,key,{"ml_quality":"0","ml_confidence":"20","ml_remediation":"Missing bib entry; rerun init or fix --bib."})
            continue
        fields={k.lower(): (v or "").strip() for k,v in (e.fields or {}).items()}
        venue = fields.get("booktitle") or fields.get("journal") or fields.get("publisher") or ""
        url = fields.get("url","").lower()
        gs = (res_cache.get(key) or {}).get("ground_signals") or {}
        sota_weak = bool(gs.get("sota_claim_weak_support"))
        # base quality
        q=85 if _is_canonical(venue) else (65 if "arxiv" in url else 50)
        # penalize blog/tooling citations used as baselines (heuristic)
        if any(x in url for x in ["blog","medium.com","substack"]):
            q -= 30
        if sota_weak:
            q -= 20
        q = max(0,min(100,q))
        c = 85 if _is_canonical(venue) else 70
        rem=[]
        if "arxiv" in url and _is_canonical(venue) is False:
            rem.append("If a proceedings version exists, cite the canonical venue (conference/journal) for core claims.")
        if sota_weak:
            rem.append("SOTA-like claim weakly supported; add direct benchmark/baseline citation or hedge.")
        if q < 60:
            rem.append("Check relevance to task/setting; consider replacing with survey/benchmark paper.")
        remediation=" | ".join(rem) if rem else "OK for ML venue lens."
        update_row(rows,key,{"ml_quality":str(q),"ml_confidence":str(c),"ml_remediation":remediation})
        if q<75:
            report.append(f"- {key}: Q={q} C={c} — {remediation}\n")

    (out_dir/"ml_report.md").write_text("".join(report), encoding="utf-8")
    write_rows_atomic(csv_path, rows, cols)
    print(f"[ml] updated {len(target_rows)} references; wrote ml_report.md (profile={profile})")
    return 0
