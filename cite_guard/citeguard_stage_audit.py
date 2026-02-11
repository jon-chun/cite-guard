from __future__ import annotations
from pathlib import Path
from citeguard_csv import load_rows, filter_rows, update_row, write_rows_atomic
from citeguard_bib_parse import parse_bib_file
from citeguard_tex_parse import parse_tex_project

PLACEHOLDER_PAT = ("tbd", "todo", "unknown", "n/a", "na", "xxx")

def run_audit(tex_path: Path, bib_path: Path, out_dir: Path, args) -> int:
    csv_path = out_dir/"audit_references.csv"
    rows, cols = load_rows(csv_path)
    target_rows = filter_rows(rows, args.only)

    entries = {e.key: e for e in parse_bib_file(bib_path)}
    try:
        citation_uses, usage_count, spans = parse_tex_project(tex_path)
    except Exception:
        usage_count = {}

    # load penalties from config
    cfg={}
    cfg_path = Path(args.config)
    if cfg_path.exists():
        try:
            from citeguard_yaml import load_yaml
            cfg = load_yaml(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            cfg={}
    pen = cfg.get("audit_penalties") or {}
    p_title = int(pen.get("missing_title",30))
    p_auth  = int(pen.get("missing_authors",30))
    p_year  = int(pen.get("missing_year",20))
    p_venue = int(pen.get("missing_venue",15))
    p_malf  = int(pen.get("malformed_bibtex",10))
    p_unused = int(pen.get("unused_reference",10))
    p_placeholder = int(pen.get("placeholder_field",10))

    report = ["# stage_audit_report\n\n"]

    for r in target_rows:
        key = r["bib_key"]
        e = entries.get(key)
        if not e:
            update_row(rows, key, {
                "audit_quality":"0","audit_confidence":"30",
                "audit_remediation":"Bib entry missing from current bib file; rerun init or fix --bib path."
            })
            continue
        fields = {k.lower(): (v or "").strip() for k,v in (e.fields or {}).items()}
        q=100
        rem=[]
        # required
        if not fields.get("title"):
            q -= p_title; rem.append("add title")
        if not fields.get("author"):
            q -= p_auth; rem.append("add authors")
        if not fields.get("year"):
            q -= p_year; rem.append("add year")
        venue = fields.get("journal") or fields.get("booktitle") or fields.get("publisher") or ""
        if not venue:
            q -= p_venue; rem.append("add venue (journal/booktitle)")
        # placeholder penalty
        for kf in ("title","author","year","journal","booktitle"):
            v = fields.get(kf,"").lower()
            if v and any(ph in v for ph in PLACEHOLDER_PAT):
                q -= p_placeholder; rem.append(f"replace placeholder in {kf}")
                break
        # unused penalty
        if usage_count and usage_count.get(key,0)==0:
            q -= p_unused; rem.append("remove unused or cite in text")
        q = max(0, min(100, q))
        # confidence heuristic
        c = 95 if q >= 70 else 80
        remediation = "Fix: " + (", ".join(dict.fromkeys(rem)) if rem else "no changes needed")
        update_row(rows, key, {
            "audit_quality": str(q),
            "audit_confidence": str(c),
            "audit_remediation": remediation
        })
        if q < 80:
            report.append(f"- {key}: Q={q} C={c} — {remediation}\n")

    (out_dir/"stage_audit_report.md").write_text("".join(report), encoding="utf-8")
    write_rows_atomic(csv_path, rows, cols)
    print(f"[audit] updated {len(target_rows)} references; wrote stage_audit_report.md")
    return 0
