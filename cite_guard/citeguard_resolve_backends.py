from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
import re, json

try:
    import requests
except Exception:
    requests = None

from citeguard_similarity import jaccard, author_overlap

@dataclass
class Candidate:
    source: str
    match_conf: float
    canonical: Dict[str, Any]
    ids: Dict[str, str]

def _req_json(url: str, params: dict, headers: dict, timeout: int) -> Optional[dict]:
    if requests is None:
        return None
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None

def resolve_crossref(title: str, author: str, year: Optional[int], timeout: int, ua: str) -> List[Candidate]:
    # Crossref works: /works?query.bibliographic=...&rows=5
    url = "https://api.crossref.org/works"
    q = title or ""
    headers={"User-Agent": ua}
    params={"query.bibliographic": q, "rows": 5}
    data = _req_json(url, params, headers, timeout)
    out=[]
    if not data:
        return out
    items = data.get("message",{}).get("items",[]) or []
    for it in items:
        ct_title = (it.get("title") or [""])[0] if isinstance(it.get("title"), list) else (it.get("title") or "")
        doi = it.get("DOI") or ""
        issued = it.get("issued",{}).get("date-parts", [[None]])[0]
        ct_year = issued[0] if issued and issued[0] else None
        auths = it.get("author",[]) or []
        auth_str = " and ".join([(a.get("family","") or "") for a in auths if a.get("family")][:12])
        mc = jaccard(title, ct_title)*0.75 + author_overlap(author, auth_str)*0.25
        if year and ct_year:
            if abs(int(year)-int(ct_year))>2:
                mc *= 0.85
        canonical = {
            "title": ct_title,
            "authors": auth_str,
            "year": ct_year,
            "venue": (it.get("container-title") or [""])[0] if isinstance(it.get("container-title"), list) else (it.get("container-title") or ""),
            "url": it.get("URL") or "",
        }
        ids={"doi": doi}
        out.append(Candidate(source="crossref", match_conf=float(mc), canonical=canonical, ids=ids))
    return out

def resolve_openalex(title: str, author: str, year: Optional[int], timeout: int, ua: str) -> List[Candidate]:
    # OpenAlex: https://api.openalex.org/works?search=...&per-page=5
    url = "https://api.openalex.org/works"
    headers={"User-Agent": ua}
    params={"search": title or "", "per-page": 5}
    data = _req_json(url, params, headers, timeout)
    out=[]
    if not data:
        return out
    for it in data.get("results",[]) or []:
        oa_title = it.get("title") or ""
        oa_year = it.get("publication_year")
        # authors list
        auths=[]
        for aa in it.get("authorships",[]) or []:
            n = aa.get("author",{}).get("display_name")
            if n:
                auths.append(n)
        auth_str = " and ".join(auths[:12])
        mc = jaccard(title, oa_title)*0.75 + author_overlap(author, auth_str)*0.25
        if year and oa_year:
            if abs(int(year)-int(oa_year))>2:
                mc *= 0.85
        ids={}
        doi = it.get("doi") or ""
        if doi:
            ids["doi"]=doi.replace("https://doi.org/","")
        # arxiv?
        for loc in it.get("locations",[]) or []:
            url_l = (loc.get("landing_page_url") or "") + " " + (loc.get("pdf_url") or "")
            m = re.search(r'arxiv\.org/(abs|pdf)/(?P<id>\d{4}\.\d{4,5})(v\d+)?', url_l)
            if m:
                ids["arxiv"]=m.group("id")
                break
        canonical = {
            "title": oa_title,
            "authors": auth_str,
            "year": oa_year,
            "venue": (it.get("primary_location") or {}).get("source",{}).get("display_name","") if it.get("primary_location") else "",
            "url": (it.get("id") or ""),
        }
        ids["openalex"]=it.get("id","")
        out.append(Candidate(source="openalex", match_conf=float(mc), canonical=canonical, ids=ids))
    return out

def resolve_arxiv(arxiv_id: str, timeout: int, ua: str) -> Optional[Candidate]:
    # arXiv API: http://export.arxiv.org/api/query?id_list=...
    if requests is None:
        return None
    import feedparser
    url = "http://export.arxiv.org/api/query"
    headers={"User-Agent": ua}
    try:
        r = requests.get(url, params={"id_list": arxiv_id}, headers=headers, timeout=timeout)
        if r.status_code != 200:
            return None
        feed = feedparser.parse(r.text)
        if not feed.entries:
            return None
        e = feed.entries[0]
        title = (e.get("title") or "").replace("\n"," ").strip()
        authors = " and ".join([a.name for a in e.get("authors",[])][:12])
        year = None
        if e.get("published"):
            year = int(e.published[:4])
        canonical={"title": title, "authors": authors, "year": year, "venue": "arXiv", "url": e.get("link","")}
        ids={"arxiv": arxiv_id}
        return Candidate(source="arxiv", match_conf=1.0, canonical=canonical, ids=ids)
    except Exception:
        return None

def resolve_dblp(title: str, timeout: int, ua: str) -> List[Candidate]:
    # DBLP API: https://dblp.org/search/publ/api?q=...&format=json&h=5
    url = "https://dblp.org/search/publ/api"
    headers={"User-Agent": ua}
    params={"q": title or "", "format":"json", "h": 5}
    data = _req_json(url, params, headers, timeout)
    out=[]
    if not data:
        return out
    hits = (((data.get("result") or {}).get("hits") or {}).get("hit") or [])
    if isinstance(hits, dict):
        hits=[hits]
    for h in hits:
        info = (h.get("info") or {})
        t = info.get("title","")
        year = info.get("year")
        venue = info.get("venue","")
        urlp = info.get("url","")
        mc = jaccard(title, t)
        canonical={"title": t, "authors": info.get("authors",""), "year": int(year) if year else None, "venue": venue, "url": urlp}
        ids={"dblp": urlp}
        out.append(Candidate(source="dblp", match_conf=float(mc), canonical=canonical, ids=ids))
    return out
