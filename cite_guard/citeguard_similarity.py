from __future__ import annotations
import re, math
from typing import Dict, List, Tuple

def normalize(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r'[^a-z0-9\s]+',' ', s)
    s = re.sub(r'\s+',' ', s).strip()
    return s

def token_set(s: str) -> set[str]:
    return set(normalize(s).split())

def jaccard(a: str, b: str) -> float:
    A = token_set(a)
    B = token_set(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)

def author_overlap(a: str, b: str) -> float:
    # crude: overlap of last-name tokens
    def last_names(s: str) -> set[str]:
        s = normalize(s)
        parts = [p.strip() for p in re.split(r'\band\b|,|;', s) if p.strip()]
        names=set()
        for p in parts:
            toks=p.split()
            if toks:
                names.add(toks[-1])
        return names
    A=last_names(a)
    B=last_names(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)
