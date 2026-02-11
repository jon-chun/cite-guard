from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re

CITE_CMD_RE = re.compile(r'\\(cite|citet|citep|autocite|parencite|textcite)\*?(?:\[[^\]]*\])?(?:\[[^\]]*\])?\{([^}]*)\}', re.IGNORECASE)
INPUT_RE = re.compile(r'\\(input|include)\{([^}]+)\}', re.IGNORECASE)
SECTION_RE = re.compile(r'\\(section|subsection|subsubsection)\*?\{([^}]*)\}', re.IGNORECASE)

@dataclass
class CitationUse:
    bib_key: str
    file: str
    line: int
    sentence: str
    section: str
    context_type: str  # abstract|conclusion|body

@dataclass
class Span:
    span_id: str
    file: str
    line_start: int
    line_end: int
    section: str
    context_type: str
    text: str

def _read_tex(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def _normalize_tex_path(base: Path, name: str) -> Path:
    # add .tex if no extension
    p = (base / name)
    if p.suffix == "":
        p = p.with_suffix(".tex")
    return p

def expand_includes(main_tex: Path, max_files: int = 200) -> List[Tuple[Path,str]]:
    base = main_tex.parent
    seen = set()
    stack = [main_tex]
    out: List[Tuple[Path,str]] = []
    while stack and len(out) < max_files:
        p = stack.pop()
        rp = p.resolve()
        if rp in seen or not p.exists():
            continue
        seen.add(rp)
        txt = _read_tex(p)
        out.append((p, txt))
        # push included files (depth-first)
        for m in INPUT_RE.finditer(txt):
            inc = m.group(2).strip()
            stack.append(_normalize_tex_path(base, inc))
    return out

def _strip_comments(line: str) -> str:
    # remove % comments not escaped
    out=[]
    esc=False
    for i,ch in enumerate(line):
        if ch == '\\':
            esc = not esc
            out.append(ch)
            continue
        if ch == '%' and not esc:
            break
        esc=False
        out.append(ch)
    return ''.join(out)

def _tex_to_text(s: str) -> str:
    # Lightweight de-TeX: remove commands, braces, math
    s = re.sub(r'\$\$.*?\$\$', ' ', s, flags=re.DOTALL)
    s = re.sub(r'\$.*?\$', ' ', s, flags=re.DOTALL)
    s = re.sub(r'\\[A-Za-z@]+\*?(\[[^\]]*\])?(\{[^}]*\})?', ' ', s)
    s = s.replace('{',' ').replace('}',' ')
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def _split_sentences(text: str) -> List[str]:
    # naive: split on .!? followed by space
    parts = re.split(r'(?<=[\.\!\?])\s+', text)
    return [p.strip() for p in parts if p.strip()]

def parse_tex_project(main_tex: Path) -> Tuple[List[CitationUse], Dict[str,int], List[Span]]:
    files = expand_includes(main_tex)
    citation_uses: List[CitationUse] = []
    usage_count: Dict[str,int] = {}
    spans: List[Span] = []
    current_section = "Unknown"
    in_abstract=False
    in_conclusion=False

    span_counter=0

    for path, txt in files:
        lines = txt.splitlines()
        for idx, raw in enumerate(lines, start=1):
            line = _strip_comments(raw)
            # section tracking
            sm = SECTION_RE.search(line)
            if sm:
                current_section = sm.group(2).strip() or current_section
                in_conclusion = (current_section.lower().startswith("conclusion") or current_section.lower().startswith("discussion"))
            if '\\begin{abstract}' in line:
                in_abstract=True
            if '\\end{abstract}' in line:
                in_abstract=False
            # simple conclusion detection: section titles handled above

            ctx = "abstract" if in_abstract else ("conclusion" if in_conclusion else "body")

            # gather citations in this line
            for cm in CITE_CMD_RE.finditer(line):
                keys_raw = cm.group(2)
                keys = [k.strip() for k in keys_raw.split(",") if k.strip()]
                # build sentence context from this line only (good enough)
                plain = _tex_to_text(line)
                sents = _split_sentences(plain) if plain else []
                sent = sents[0] if sents else plain
                for k in keys:
                    citation_uses.append(CitationUse(
                        bib_key=k,
                        file=str(path),
                        line=idx,
                        sentence=sent,
                        section=current_section,
                        context_type=ctx
                    ))
                    usage_count[k]=usage_count.get(k,0)+1

            # spans: store abstract and conclusion spans plus any line with cite
            if in_abstract or in_conclusion or CITE_CMD_RE.search(line):
                span_counter += 1
                spans.append(Span(
                    span_id=f"S{span_counter:05d}",
                    file=str(path),
                    line_start=idx,
                    line_end=idx,
                    section=current_section,
                    context_type=ctx,
                    text=_tex_to_text(line)
                ))

    return citation_uses, usage_count, spans
