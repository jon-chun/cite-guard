from __future__ import annotations
from pathlib import Path
import json, re
from citeguard_csv import load_rows, filter_rows, update_row, write_rows_atomic
from citeguard_bib_parse import parse_bib_file
from citeguard_similarity import jaccard, author_overlap
from citeguard_resolve_backends import resolve_openalex, resolve_crossref, resolve_dblp, resolve_arxiv

def _int(x):
    try:
        return int(x)
    except Exception:
        return None

def run_resolve(tex_path: Path, bib_path: Path, out_dir: Path, args) -> int:
    csv_path = out_dir / "audit_references.csv"
    rows, cols = load_rows(csv_path)
    target_rows = filter_rows(rows, args.only)
    entries = {e.key: e for e in parse_bib_file(bib_path)}

    # config: try reading YAML file if present (optional). We'll keep simple.
    cfg_path = Path(args.config)
    cfg = {}
    if cfg_path.exists():
        try:
            from citeguard_yaml import load_yaml
            cfg = load_yaml(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    thr = (cfg.get("resolve_thresholds") or {})
    pass_t = float(thr.get("title_similarity_pass", 0.92))
    pass_a = float(thr.get("author_overlap_pass", 0.70))
    pass_y = int(thr.get("year_diff_pass", 1))
    review_t = float(thr.get("title_similarity_review", 0.86))
    review_a = float(thr.get("author_overlap_review", 0.55))
    max_cand = int(thr.get("max_candidates", 3))

    timeout = int((cfg.get("http_timeout_sec") or 25))
    ua = str(cfg.get("user_agent") or "refqa/1.0")

    cache_path = out_dir / "resolution_cache.json"
    cache = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    corrected_bib = []

    report_lines = ["# stage_resolve_report\n"]

    for r in target_rows:
        key = r["bib_key"]
        e = entries.get(key)
        if not e:
            update_row(rows, key, {
                "resolve_quality":"0","resolve_confidence":"20",
                "resolve_remediation":"Bib entry missing from current bib file; rerun init with correct --bib."
            })
            continue
        fields = {k.lower(): v for k,v in (e.fields or {}).items()}
        title = fields.get("title","")
        author = fields.get("author","")
        year = _int(fields.get("year"))
        venue = fields.get("journal") or fields.get("booktitle") or fields.get("publisher") or ""
        doi = fields.get("doi","")
        arxiv_id = fields.get("eprint","") or ""
        if not arxiv_id:
            # common patterns
            url = fields.get("url","")
            m = re.search(r'arxiv\.org/(abs|pdf)/(?P<id>\d{4}\.\d{4,5})', url or "")
            if m:
                arxiv_id = m.group("id")

        best = None
        candidates = []

        # 1) DOI exact: verify by querying OpenAlex/Crossref search by title; true DOI verification requires resolution
        if doi:
            # quick check: store doi, later compare if a candidate has same doi
            pass

        # 2) arXiv exact
        if arxiv_id:
            cand = resolve_arxiv(arxiv_id, timeout=timeout, ua=ua)
            if cand:
                candidates.append(cand)

        # 3) OpenAlex and Crossref fuzzy
        if title:
            candidates += resolve_openalex(title, author, year, timeout=timeout, ua=ua)
            candidates += resolve_crossref(title, author, year, timeout=timeout, ua=ua)
            candidates += resolve_dblp(title, timeout=timeout, ua=ua)

        # pick best candidate by match_conf, boost if doi matches
        for c in candidates:
            mc = c.match_conf
            if doi and c.ids.get("doi","").lower().strip() == doi.lower().strip():
                mc = min(1.0, mc + 0.10)
            if arxiv_id and c.ids.get("arxiv","") == arxiv_id:
                mc = min(1.0, mc + 0.10)
            if (best is None) or mc > best.match_conf:
                best = type(c)(source=c.source, match_conf=mc, canonical=c.canonical, ids=c.ids)

        if best is None:
            update_row(rows, key, {
                "resolve_quality":"10","resolve_confidence":"20",
                "resolve_remediation":"Unresolved: add DOI or arXiv ID; verify title/authors; replace if non-existent."
            })
            cache[key]={"status":"unresolved","candidates":[]}
            report_lines.append(f"- {key}: unresolved\n")
            continue

        # compute title and author overlaps against canonical
        can_title = best.canonical.get("title","")
        can_auth = best.canonical.get("authors","")
        can_year = best.canonical.get("year")
        ts = jaccard(title, can_title)
        ao = author_overlap(author, can_auth)
        yd = abs((year or can_year or 0) - (can_year or year or 0)) if (year or can_year) else 99

        status = "needs_review"
        if ts >= pass_t and ao >= pass_a and yd <= pass_y:
            status = "resolved"
        elif ts >= review_t and ao >= review_a:
            status = "needs_review"
        else:
            status = "unresolved"

        # quality/confidence mapping
        if status == "resolved":
            q = 95
            c = int(min(100, 70 + best.match_conf*30))
            rem = "OK: resolved to canonical record; consider updating BibTeX with refs.corrected.bib."
        elif status == "needs_review":
            q = 65
            c = int(min(90, 50 + best.match_conf*40))
            rem = "Review match: add DOI/arXiv ID and reconcile title/authors/year with canonical metadata."
        else:
            q = 25
            c = int(min(60, 30 + best.match_conf*30))
            rem = "Likely mismatch/hallucination: verify existence; add DOI/arXiv; replace with verifiable source."

        # mismatch flags
        mismatch=[]
        if year and can_year and int(year)!=int(can_year):
            mismatch.append(f"year_mismatch(bib={year},can={can_year})")
        if venue and best.canonical.get("venue") and venue.lower() not in str(best.canonical.get('venue','')).lower():
            mismatch.append("venue_mismatch")

        cache[key]={
            "status": status,
            "match_confidence": best.match_conf,
            "canonical": best.canonical,
            "ids": best.ids,
            "signals": {"title_similarity": ts, "author_overlap": ao, "year_diff": yd},
            "mismatch": mismatch
        }

        update_row(rows, key, {
            "resolve_quality": str(q),
            "resolve_confidence": str(c),
            "resolve_remediation": rem
        })

        report_lines.append(f"- {key}: {status} (title_sim={ts:.2f}, author_overlap={ao:.2f}, year_diff={yd}) {';'.join(mismatch)}\n")

        # corrected bib entry if resolved
        if status == "resolved":
            # rewrite minimal BibTeX using original type and key; set title/author/year/url/doi
            can = best.canonical
            can_doi = best.ids.get("doi","") or fields.get("doi","")
            can_url = can.get("url","") or fields.get("url","")
            can_authors = can.get("authors","") or fields.get("author","")
            can_year_s = str(can.get("year") or fields.get("year",""))
            can_title_s = can.get("title","") or fields.get("title","")
            can_venue = can.get("venue","") or venue
            entry_type = e.entry_type
            # choose field name for venue
            venue_field = "journal" if entry_type in ("article",) else "booktitle"
            bib = [f"@{entry_type}{{{key},"]
            bib.append(f"  title={{ {can_title_s} }},")
            if can_authors:
                bib.append(f"  author={{ {can_authors} }},")
            if can_year_s:
                bib.append(f"  year={{ {can_year_s} }},")
            if can_venue:
                bib.append(f"  {venue_field}={{ {can_venue} }},")
            if can_doi:
                bib.append(f"  doi={{ {can_doi} }},")
            if can_url:
                bib.append(f"  url={{ {can_url} }},")
            bib.append("}\n")
            corrected_bib.append("\n".join(bib))

    (out_dir/"stage_resolve_report.md").write_text("".join(report_lines), encoding="utf-8")
    cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    (out_dir/"refs.corrected.bib").write_text("\n\n".join(corrected_bib), encoding="utf-8")

    write_rows_atomic(csv_path, rows, cols)
    print(f"[resolve] updated {len(target_rows)} references; wrote resolution_cache.json, refs.corrected.bib")
    return 0
