from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict
import re, os, time, json

try:
    import requests
except Exception:
    requests = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

@dataclass
class EvidenceArtifact:
    url: str
    path: str
    fmt: str
    bytes: int

def _safe_filename(s: str) -> str:
    s = re.sub(r'[^A-Za-z0-9._-]+','_',s)
    return s[:160]

def fetch_url(url: str, out_dir: Path, timeout: int, max_bytes: int, user_agent: str) -> Optional[EvidenceArtifact]:
    if requests is None:
        return None
    headers = {"User-Agent": user_agent}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, stream=True)
        if r.status_code != 200:
            return None
        content = b""
        size=0
        for chunk in r.iter_content(chunk_size=65536):
            if not chunk:
                continue
            content += chunk
            size += len(chunk)
            if size > max_bytes:
                return None
        # infer fmt
        ct = (r.headers.get("content-type","") or "").lower()
        fmt = "bin"
        if "text/markdown" in ct or url.lower().endswith(".md"):
            fmt="md"
        elif "text/html" in ct or url.lower().endswith((".html",".htm")):
            fmt="html"
        elif url.lower().endswith(".tex"):
            fmt="tex"
        elif url.lower().endswith(".rtf"):
            fmt="rtf"
        elif "text/plain" in ct or url.lower().endswith(".txt"):
            fmt="txt"
        elif "application/pdf" in ct or url.lower().endswith(".pdf"):
            fmt="pdf"
        name = _safe_filename(url.split("/")[-1] or "artifact")
        if "." not in name and fmt in ("md","html","tex","rtf","txt","pdf"):
            name = f"{name}.{fmt}"
        path = out_dir / name
        path.write_bytes(content)
        return EvidenceArtifact(url=url, path=str(path), fmt=fmt, bytes=size)
    except Exception:
        return None

def extract_text_from_artifact(artifact: EvidenceArtifact) -> str:
    p = Path(artifact.path)
    if artifact.fmt in ("md","txt","tex","rtf"):
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
    if artifact.fmt == "html":
        try:
            html = p.read_text(encoding="utf-8", errors="ignore")
            if BeautifulSoup is None:
                # crude strip tags
                return re.sub(r'<[^>]+>',' ', html)
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text("\n")
        except Exception:
            return ""
    if artifact.fmt == "pdf":
        if PyPDF2 is None:
            return ""
        try:
            reader = PyPDF2.PdfReader(str(p))
            texts=[]
            for page in reader.pages[:25]:  # cap pages for lightweight
                t = page.extract_text() or ""
                if t:
                    texts.append(t)
            return "\n".join(texts)
        except Exception:
            return ""
    return ""

def discover_linked_artifacts(landing_url: str, prefer_exts: List[str], out_dir: Path, timeout: int, max_bytes: int, user_agent: str) -> List[EvidenceArtifact]:
    """Fetch landing page HTML and look for links to preferred extensions."""
    arts: List[EvidenceArtifact] = []
    if requests is None:
        return arts
    headers={"User-Agent": user_agent}
    try:
        r = requests.get(landing_url, headers=headers, timeout=timeout)
        if r.status_code != 200:
            return arts
        html = r.text
        if BeautifulSoup is None:
            hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        else:
            soup = BeautifulSoup(html, "html.parser")
            hrefs = [a.get("href") for a in soup.find_all("a") if a.get("href")]
        # normalize relative
        from urllib.parse import urljoin
        cand=[]
        for h in hrefs:
            u = urljoin(landing_url, h)
            cand.append(u)
        # select unique by preference
        selected=[]
        for ext in prefer_exts:
            for u in cand:
                if u.lower().endswith("."+ext) and u not in selected:
                    selected.append(u)
        # fetch top few
        for u in selected[:8]:
            art = fetch_url(u, out_dir, timeout, max_bytes, user_agent)
            if art:
                arts.append(art)
        return arts
    except Exception:
        return arts
