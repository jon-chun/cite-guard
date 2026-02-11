from __future__ import annotations
from pathlib import Path
import json, re
from citeguard_csv import load_rows, filter_rows, update_row, write_rows_atomic
from citeguard_yaml import load_yaml
from citeguard_bib_parse import parse_bib_file

def _genre_from_fields(url: str, entry_type: str, venue: str) -> str:
    u=(url or "").lower()
    v=(venue or "").lower()
    if "arxiv.org" in u or entry_type in ("misc","unpublished"):
        return "preprint"
    if any(x in v for x in ["standard","iso","nist","ietf","w3c","oecd","uk","eu","commission","parliament","house of commons","ofcom","ico"]):
        return "primary_policy"
    if any(x in u for x in ["gov.uk","europa.eu","legislation.gov.uk"]):
        return "primary_policy"
    if any(x in u for x in ["blog","medium.com","substack","newsletter"]):
        return "blog"
    if entry_type in ("article","inproceedings","book","incollection"):
        return "scholarly"
    return "other"

def run_venue(tex_path: Path, bib_path: Path, out_dir: Path, args) -> int:
    cfg={}
    cfg_path=Path(args.config)
    if cfg_path.exists():
        cfg=load_yaml(cfg_path.read_text(encoding="utf-8"))
    profile = (args.venue_profile or cfg.get("venue_profile") or "policy_generic").lower()

    csv_path = out_dir/"audit_references.csv"
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

    report=["# venue_report\n\n"]

    for r in target_rows:
        key=r["bib_key"]
        e=entries.get(key)
        if not e:
            update_row(rows,key,{"venue_quality":"0","venue_confidence":"20","venue_remediation":"Missing bib entry; rerun init or fix --bib."})
            continue
        fields={k.lower(): (v or "").strip() for k,v in (e.fields or {}).items()}
        url = fields.get("url","")
        venue = fields.get("journal") or fields.get("booktitle") or fields.get("publisher") or ""
        genre=_genre_from_fields(url, e.entry_type, venue)
        # use ground signals if present
        gs = (res_cache.get(key) or {}).get("ground_signals") or {}
        high_priority_fail = bool(gs.get("high_priority_claim_unsupported"))
        # base score
        q=85 if genre in ("scholarly","primary_policy") else (55 if genre=="preprint" else (35 if genre=="blog" else 50))
        # penalize if used in high priority policy claims and not authoritative
        if high_priority_fail and genre in ("blog","other"):
            q -= 20
        q = max(0,min(100,q))
        c = 85 if genre in ("scholarly","primary_policy") else 70
        rem=[]
        if genre=="blog":
            rem.append("Replace blog with peer-reviewed paper, authoritative report, or primary policy source for normative claims.")
        if genre=="preprint":
            rem.append("If used for policy claims, add authoritative report/standard/regulator guidance; preprints are weaker authority.")
        if high_priority_fail:
            rem.append("High-priority claim unsupported: strengthen evidence or hedge claim language.")
        remediation=" | ".join(rem) if rem else "OK for policy lens; ensure authority matches claim type."
        update_row(rows,key,{"venue_quality":str(q),"venue_confidence":str(c),"venue_remediation":remediation})
        if q<75:
            report.append(f"- {key}: genre={genre} Q={q} C={c} — {remediation}\n")

    (out_dir/"venue_report.md").write_text("".join(report), encoding="utf-8")
    write_rows_atomic(csv_path, rows, cols)
    print(f"[venue] updated {len(target_rows)} references; wrote venue_report.md (profile={profile})")
    return 0
