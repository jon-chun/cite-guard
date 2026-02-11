from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple
import re

@dataclass
class Claim:
    claim_id: str
    section: str
    context_type: str  # abstract|conclusion|body
    file: str
    line: int
    claim_text: str
    cited_keys: List[str]
    priority: str  # high|normal|low
    is_sota: bool
    strength: str  # strong|medium|weak

def classify_strength(text: str, strong_verbs: List[str]) -> str:
    t=text.lower()
    if any(v in t for v in strong_verbs):
        return "strong"
    if any(w in t for w in ["may","might","could","suggest","indicate","often","typically","likely"]):
        return "weak"
    return "medium"

def detect_sota(text: str, sota_keywords: List[str]) -> bool:
    t=text.lower()
    return any(k.lower() in t for k in sota_keywords)

def extract_claims_from_citations(citation_uses, sota_keywords: List[str], strong_verbs: List[str]) -> List[Claim]:
    # Build claims from each unique (file,line,sentence,section,context_type)
    seen=set()
    claims=[]
    cid=0
    # group cite keys per sentence
    bucket: Dict[tuple, set[str]] = {}
    for cu in citation_uses:
        k=(cu.file, cu.line, cu.sentence, cu.section, cu.context_type)
        bucket.setdefault(k,set()).add(cu.bib_key)
    for (file,line,sent,section,ctx), keys in bucket.items():
        txt = sent.strip()
        if len(txt.split()) < 6:
            continue
        cid += 1
        priority = "high" if ctx in ("abstract","conclusion") else "normal"
        claims.append(Claim(
            claim_id=f"C{cid:05d}",
            section=section,
            context_type=ctx,
            file=file,
            line=line,
            claim_text=txt,
            cited_keys=sorted(keys),
            priority=priority,
            is_sota=detect_sota(txt, sota_keywords),
            strength=classify_strength(txt, strong_verbs)
        ))
    return claims

def extract_uncited_high_priority_sentences(spans, max_sentences: int = 80) -> List[Claim]:
    # Create claims from abstract/conclusion spans even without citations (for blocker rule).
    claims=[]
    cid=0
    for sp in spans:
        if sp.context_type not in ("abstract","conclusion"):
            continue
        txt = (sp.text or "").strip()
        if len(txt.split()) < 10:
            continue
        cid += 1
        claims.append(Claim(
            claim_id=f"HC{cid:05d}",
            section=sp.section,
            context_type=sp.context_type,
            file=sp.file,
            line=sp.line_start,
            claim_text=txt,
            cited_keys=[],
            priority="high",
            is_sota=False,
            strength="medium"
        ))
        if len(claims) >= max_sentences:
            break
    return claims
