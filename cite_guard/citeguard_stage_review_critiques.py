from __future__ import annotations
from pathlib import Path
import csv, json
from citeguard_csv import load_rows, write_rows_atomic
from citeguard_yaml import load_yaml

STAGES = ["audit","resolve","ground","venue","ml"]

def conf_weight(conf: float, mode: str) -> float:
    c = max(0.0, min(1.0, conf/100.0))
    if mode == "equal":
        return 1.0
    if mode == "quadratic":
        return c*c
    return c

def parse_weights(s: str | None) -> dict[str,float]:
    if not s:
        return {st: 1.0 for st in STAGES}
    weights={}
    for part in s.split(","):
        k,v = part.split("=")
        weights[k.strip()] = float(v.strip())
    for st in STAGES:
        weights.setdefault(st, 1.0)
    return weights

# Blocker checks return (is_blocker, note)
def blocker_resolve_unresolved_or_low_conf(r: dict, cfg: dict) -> tuple[bool,str]:
    thr = cfg.get("priority_thresholds") or {}
    qlt = float(thr.get("blocker_resolve_quality_lt",40))
    clt = float(thr.get("blocker_resolve_confidence_lt",50))
    rq = float(r.get("resolve_quality","0") or 0)
    rc = float(r.get("resolve_confidence","0") or 0)
    if rq < qlt or rc < clt:
        return True, "Resolve stage unresolved/low-confidence."
    return False, ""

def blocker_year_or_venue_mismatch_after_resolve(r: dict, res_cache: dict) -> tuple[bool,str]:
    key=r.get("bib_key","")
    mis = (res_cache.get(key) or {}).get("mismatch") or []
    if any("year_mismatch" in m for m in mis) or any("venue_mismatch"==m for m in mis):
        return True, "Year/venue mismatch after resolution; reconcile BibTeX with canonical."
    return False, ""

def blocker_high_priority_claim_unsupported(r: dict, res_cache: dict) -> tuple[bool,str]:
    key=r.get("bib_key","")
    gs = (res_cache.get(key) or {}).get("ground_signals") or {}
    if gs.get("high_priority_claim_unsupported"):
        return True, "High-priority (abstract/conclusion) claim unsupported for this reference usage."
    return False, ""

def blocker_sota_claim_with_unresolved_or_low_conf_ref(r: dict, res_cache: dict, cfg: dict) -> tuple[bool,str]:
    key=r.get("bib_key","")
    gs = (res_cache.get(key) or {}).get("ground_signals") or {}
    if not gs.get("sota_claim_weak_support"):
        return False, ""
    # if SOTA is weak AND resolve is not strong, blocker
    rq = float(r.get("resolve_quality","0") or 0)
    rc = float(r.get("resolve_confidence","0") or 0)
    if rq < 70 or rc < 70:
        return True, "SOTA-like claim uses weakly grounded reference with non-strong resolution; add canonical/benchmark citations."
    return False, ""

BLOCKER_FUNCS = {
    "resolve_unresolved_or_low_confidence": blocker_resolve_unresolved_or_low_conf,
    "year_or_venue_mismatch_after_resolve": blocker_year_or_venue_mismatch_after_resolve,
    "high_priority_claim_unsupported": blocker_high_priority_claim_unsupported,
    "sota_claim_with_unresolved_or_low_conf_ref": blocker_sota_claim_with_unresolved_or_low_conf_ref,
}

def run_review_critiques(tex_path: Path, bib_path: Path, out_dir: Path, args) -> int:
    cfg={}
    cfg_path=Path(args.config)
    if cfg_path.exists():
        cfg=load_yaml(cfg_path.read_text(encoding="utf-8"))

    csv_path = out_dir/"audit_references.csv"
    rows, cols = load_rows(csv_path)

    weights = parse_weights(getattr(args,"weights",None)) or (cfg.get("weights") or {st:1.0 for st in STAGES})
    mode = getattr(args,"confidence_weighting",None) or (cfg.get("confidence_weighting") or "linear")

    # profile selection
    profile = (getattr(args,"rules_profile",None) or getattr(args,"ml_profile",None) or cfg.get("ml_profile") or "default").lower()
    review_cfg = cfg.get("review") or {}
    default_blockers = [b for b in (review_cfg.get("default_blockers") or [])]
    profile_blockers = [b for b in ((review_cfg.get("profiles") or {}).get(profile, {}) or {}).get("blockers", [])]

    # load resolution cache for mismatch + ground signals
    res_cache_path = out_dir/"resolution_cache.json"
    res_cache={}
    if res_cache_path.exists():
        try:
            res_cache=json.loads(res_cache_path.read_text(encoding="utf-8"))
        except Exception:
            res_cache={}

    # compute scores + priorities
    for r in rows:
        total_w=0.0
        accum=0.0
        for st in STAGES:
            q=float(r.get(f"{st}_quality","0") or 0)
            c=float(r.get(f"{st}_confidence","0") or 0)
            w=float(weights.get(st, 1.0))
            total_w += w
            accum += w * (q/100.0) * conf_weight(c, mode)
        score = 0.0 if total_w==0 else 100.0*(accum/total_w)
        r["reference_quality_score"]=f"{score:.1f}"

        blocker_notes=[]
        # default blockers
        for b in default_blockers:
            fn = BLOCKER_FUNCS.get(b)
            if not fn:
                continue
            if b=="resolve_unresolved_or_low_confidence":
                ok, note = fn(r, cfg)
            elif b in ("year_or_venue_mismatch_after_resolve","high_priority_claim_unsupported"):
                ok, note = fn(r, res_cache)
            else:
                ok, note = fn(r, res_cache, cfg)
            if ok:
                blocker_notes.append(note)
        # profile blockers
        for b in profile_blockers:
            fn = BLOCKER_FUNCS.get(b)
            if not fn:
                continue
            if b=="resolve_unresolved_or_low_confidence":
                ok, note = fn(r, cfg)
            elif b in ("year_or_venue_mismatch_after_resolve","high_priority_claim_unsupported"):
                ok, note = fn(r, res_cache)
            else:
                ok, note = fn(r, res_cache, cfg)
            if ok and note not in blocker_notes:
                blocker_notes.append(note)

        if blocker_notes:
            r["review_priority"]="blocker"
            r["reference_quality_notes"]=" | ".join(blocker_notes)
        else:
            # non-blocker priority fallback
            thr = cfg.get("priority_thresholds") or {}
            high_ground = float(thr.get("high_ground_quality_lt",50))
            med_venue = float(thr.get("medium_venue_quality_lt",60))
            ground_q = float(r.get("ground_quality","0") or 0)
            venue_q = float(r.get("venue_quality","0") or 0)
            if ground_q < high_ground:
                r["review_priority"]="high"
                r["reference_quality_notes"]="Weak grounding support for claims citing this reference."
            elif venue_q < med_venue:
                r["review_priority"]="medium"
                r["reference_quality_notes"]="Weak policy/governance fit for its usage."
            else:
                r["review_priority"]="low"
                r["reference_quality_notes"]="No blocker triggered; scores acceptable."

    ranked = sorted(rows, key=lambda x: float(x.get("reference_quality_score","0") or 0))
    out_csv = out_dir/"review_critiques.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(ranked)

    out_md = out_dir/"review_critiques.md"
    lines=[f"# review_critiques (ranked) — profile={profile}\n\n"]
    for i,r in enumerate(ranked[:100], start=1):
        lines.append(f"## {i}. {r['bib_key']} — score {r['reference_quality_score']} — {r['review_priority']}\n")
        lines.append(f"- Notes: {r.get('reference_quality_notes','')}\n")
        for st in STAGES:
            lines.append(f"  - {st}: Q={r.get(st+'_quality')} C={r.get(st+'_confidence')} — {r.get(st+'_remediation')}\n")
        lines.append("\n")
    out_md.write_text("".join(lines), encoding="utf-8")

    write_rows_atomic(csv_path, rows, cols)
    print(f"[review_critiques] wrote {out_csv}, {out_md}, updated {csv_path} (profile={profile})")
    return 0
