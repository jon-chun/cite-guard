from __future__ import annotations
from pathlib import Path
import json, re
from typing import Dict, List, Tuple
from citeguard_csv import load_rows, filter_rows, update_row, write_rows_atomic
from citeguard_tex_parse import parse_tex_project
from citeguard_bib_parse import parse_bib_file
from citeguard_yaml import load_yaml
from citeguard_claims import extract_claims_from_citations, extract_uncited_high_priority_sentences
from citeguard_similarity import normalize, token_set, jaccard
from citeguard_evidence import fetch_url, discover_linked_artifacts, extract_text_from_artifact

def _safe_mkdir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def _top_snippets(claim: str, text: str, k: int = 3) -> List[str]:
    # pick top k paragraphs by jaccard overlap with claim tokens
    claim_toks = token_set(claim)
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    scored=[]
    for p in paras[:200]:
        ptoks = token_set(p)
        if not ptoks:
            continue
        overlap = len(claim_toks & ptoks) / max(1, len(claim_toks))
        scored.append((overlap, p))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [p for _,p in scored[:k]]

def _verdict_from_overlap(overlap: float, neg_hit: bool, supported_thr: float, weak_thr: float) -> Tuple[str,float]:
    # crude: overlap acts like confidence; negation flips to contradicted if high
    conf = max(0.0, min(1.0, overlap))
    if neg_hit and conf >= supported_thr:
        return ("contradicted", conf)
    if conf >= supported_thr:
        return ("supported", conf)
    if conf >= weak_thr:
        return ("weakly_supported", conf)
    return ("unsupported", conf)

def run_ground(tex_path: Path, bib_path: Path, out_dir: Path, args) -> int:
    cfg = {}
    cfg_path = Path(args.config)
    if cfg_path.exists():
        cfg = load_yaml(cfg_path.read_text(encoding="utf-8"))
    evidence_pref = cfg.get("evidence_preference") or ["md","html","htm","tex","rtf","txt","pdf"]
    timeout = int(cfg.get("http_timeout_sec") or 25)
    max_bytes = int(cfg.get("http_max_bytes") or 15000000)
    ua = str(cfg.get("user_agent") or "refqa/1.0")
    fetch_enabled = bool(cfg.get("ground_fetch_enabled", True))
    if getattr(args, "fetch", False):
        fetch_enabled = True
    if getattr(args, "no_fetch", False):
        fetch_enabled = False

    grounding_cfg = cfg.get("grounding") or {}
    supported_thr = float(grounding_cfg.get("supported_threshold", 0.75))
    weak_thr = float(grounding_cfg.get("weak_threshold", 0.60))
    sota_keywords = grounding_cfg.get("sota_keywords") or []
    strong_verbs = grounding_cfg.get("strong_claim_verbs") or []
    neg_tokens = set((grounding_cfg.get("negation_tokens") or []))

    csv_path = out_dir/"audit_references.csv"
    rows, cols = load_rows(csv_path)
    target_rows = filter_rows(rows, args.only)

    entries = {e.key: e for e in parse_bib_file(bib_path)}

    citation_uses, usage_count, spans = parse_tex_project(tex_path)
    claims = extract_claims_from_citations(citation_uses, sota_keywords, strong_verbs)
    claims += extract_uncited_high_priority_sentences(spans)

    _safe_mkdir(out_dir/"evidence_cache")
    # load resolution cache for URLs/ids
    res_cache_path = out_dir/"resolution_cache.json"
    res_cache = {}
    if res_cache_path.exists():
        try:
            res_cache = json.loads(res_cache_path.read_text(encoding="utf-8"))
        except Exception:
            res_cache = {}

    # Build claim map per reference key
    claims_by_ref: Dict[str, List[dict]] = {}
    for cl in claims:
        for k in cl.cited_keys:
            claims_by_ref.setdefault(k, []).append({
                "claim_id": cl.claim_id,
                "text": cl.claim_text,
                "priority": cl.priority,
                "context_type": cl.context_type,
                "is_sota": cl.is_sota,
                "strength": cl.strength,
                "file": cl.file,
                "line": cl.line,
                "section": cl.section
            })

    # save claims
    (out_dir/"claims.json").write_text(json.dumps([cl.__dict__ for cl in claims], indent=2), encoding="utf-8")

    # evidence cache map
    evidence_index = {}

    grounding_report = ["# grounding_report\n\n"]
    rewrites = ["% rewrites.tex (generated)\n\n"]

    # helper: build candidate evidence URLs
    def candidate_urls_for_ref(key: str) -> List[str]:
        can = (res_cache.get(key) or {}).get("canonical") or {}
        ids = (res_cache.get(key) or {}).get("ids") or {}
        urls=[]
        # openalex id isn't a paper; but may include doi/arxiv
        doi = ids.get("doi","")
        arx = ids.get("arxiv","")
        if doi:
            urls.append(f"https://doi.org/{doi}")
        if arx:
            urls.append(f"https://arxiv.org/abs/{arx}")
            urls.append(f"https://arxiv.org/pdf/{arx}.pdf")
        # bib url
        url_field = (entries.get(key).fields.get("url") if entries.get(key) else None) or ""
        if url_field:
            urls.append(url_field)
        # fall back to canonical url if any
        if can.get("url"):
            urls.append(can.get("url"))
        # unique preserve order
        seen=set(); out=[]
        for u in urls:
            if u and u not in seen:
                seen.add(u); out.append(u)
        return out

    # Heuristic grounding per reference
    for r in target_rows:
        key = r["bib_key"]
        ref_claims = claims_by_ref.get(key, [])
        if not ref_claims:
            # not cited; neutral ground score, but low confidence
            update_row(rows, key, {
                "ground_quality":"70",
                "ground_confidence":"40",
                "ground_remediation":"Reference not cited in TeX; remove if unintended, or add intended citation context."
            })
            continue

        # fetch evidence (best effort)
        text_blob=""
        evidence_conf = 0.0
        chosen_art=None
        if fetch_enabled:
            ref_dir = out_dir/"evidence_cache"/key
            _safe_mkdir(ref_dir)
            urls = candidate_urls_for_ref(key)
            artifacts=[]
            # try direct fetch for preferred exts from urls
            for u in urls:
                # If URL points to PDF/html etc, fetch directly
                art = fetch_url(u, ref_dir, timeout, max_bytes, ua)
                if art:
                    artifacts.append(art)
                # If we fetched html, also discover linked artifacts
                if u.lower().endswith((".html",".htm")) or (art and art.fmt=="html") or ("arxiv.org/abs/" in u):
                    artifacts += discover_linked_artifacts(u, evidence_pref, ref_dir, timeout, max_bytes, ua)
                if len(artifacts) >= 6:
                    break
            # pick best artifact by preference order
            pref_rank={ext:i for i,ext in enumerate(evidence_pref)}
            artifacts_sorted = sorted(artifacts, key=lambda a: pref_rank.get(a.fmt, 99))
            if artifacts_sorted:
                chosen_art = artifacts_sorted[0]
                text_blob = extract_text_from_artifact(chosen_art)
                evidence_conf = 0.9 if chosen_art.fmt in ("md","html","txt","tex") else (0.75 if chosen_art.fmt=="pdf" else 0.5)
                evidence_index[key]={"chosen": chosen_art.__dict__, "all":[a.__dict__ for a in artifacts_sorted[:10]]}
        else:
            evidence_index[key]={"chosen": None, "all":[]}

        # evaluate each claim
        verdict_points=[]
        hp_fail=False
        sota_risky=False
        for cl in ref_claims:
            claim_text = cl["text"]
            if not text_blob:
                verdict="unsupported"; conf=0.0; overlap=0.0
            else:
                snippets = _top_snippets(claim_text, text_blob, k=3)
                # overlap against best snippet
                best_overlap=0.0
                best_snip=""
                for sn in snippets:
                    ov = jaccard(claim_text, sn)
                    if ov > best_overlap:
                        best_overlap=ov; best_snip=sn
                neg_hit = any(tok in best_snip.lower() for tok in neg_tokens)
                verdict, conf = _verdict_from_overlap(best_overlap, neg_hit, supported_thr, weak_thr)
                overlap=best_overlap

            pts = 1.0 if verdict=="supported" else (0.6 if verdict=="weakly_supported" else (0.0 if verdict=="unsupported" else -0.5))
            verdict_points.append(pts)

            # high-priority failure flag for NeurIPS blocker
            if cl["priority"]=="high" and verdict in ("unsupported","contradicted"):
                hp_fail=True
                # propose rewrite (very simple hedge)
                rewrites.append(f"% {cl['file']}:{cl['line']}\n% Original: {cl['text']}\n")
                rewrites.append(f"% Suggested: (needs evidence) Consider hedging: "{cl['text']}" -> "{cl['text'].replace('demonstrates','suggests').replace('proves','suggests')}"\n\n")

            # SOTA risk: if claim is SOTA and evidence weak OR ref unresolved
            if cl.get("is_sota") and verdict in ("unsupported","weakly_supported"):
                sota_risky=True

        avg_pts = sum(verdict_points)/len(verdict_points) if verdict_points else 0.6
        ground_quality = max(0, min(100, (avg_pts + 0.5)/1.5 * 100))
        ground_conf = int(max(10, min(100, evidence_conf*100)))

        rem = []
        if not text_blob:
            rem.append("Fetch evidence (enable --fetch) or provide local PDFs/text for grounding.")
        if hp_fail:
            rem.append("High-priority (abstract/conclusion) claim unsupported: rewrite or add stronger citation.")
        if sota_risky:
            rem.append("SOTA-like claim weakly supported: add direct benchmark/baseline citation or hedge language.")
        remediation = " | ".join(rem) if rem else "OK: evidence supports usage; ensure citations match exact setting."

        update_row(rows, key, {
            "ground_quality": f"{ground_quality:.0f}",
            "ground_confidence": str(ground_conf),
            "ground_remediation": remediation
        })

        grounding_report.append(f"## {key}\n- ground_quality={ground_quality:.0f} ground_confidence={ground_conf}\n- remediation: {remediation}\n\n")

        # store signals for review stage
        res_cache.setdefault(key, {})
        res_cache[key].setdefault("ground_signals", {})
        res_cache[key]["ground_signals"].update({
            "high_priority_claim_unsupported": hp_fail,
            "sota_claim_weak_support": sota_risky,
            "evidence_format": (chosen_art.fmt if chosen_art else None),
            "evidence_available": bool(text_blob)
        })

    (out_dir/"grounding_report.md").write_text("".join(grounding_report), encoding="utf-8")
    (out_dir/"rewrites.tex").write_text("".join(rewrites), encoding="utf-8")
    (out_dir/"evidence_index.json").write_text(json.dumps(evidence_index, indent=2), encoding="utf-8")
    # update cache with ground signals
    res_cache_path.write_text(json.dumps(res_cache, indent=2), encoding="utf-8")

    write_rows_atomic(csv_path, rows, cols)
    print(f"[ground] updated {len(target_rows)} references; wrote claims.json, grounding_report.md, rewrites.tex")
    return 0
