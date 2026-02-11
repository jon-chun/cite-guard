from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
import re

@dataclass
class BibEntry:
    key: str
    entry_type: str
    raw: str
    fields: Dict[str,str]

_ENTRY_RE = re.compile(r'@(?P<type>\w+)\s*\{\s*(?P<key>[^,\s]+)\s*,', re.IGNORECASE)

def _strip_outer_braces(s: str) -> str:
    s = s.strip()
    if (s.startswith("{") and s.endswith("}")) or (s.startswith('"') and s.endswith('"')):
        return s[1:-1].strip()
    return s

def _parse_fields(body: str) -> Dict[str,str]:
    # Simple BibTeX field parser supporting nested braces with a small state machine.
    fields: Dict[str,str] = {}
    i=0
    n=len(body)
    while i<n:
        # skip whitespace/commas
        while i<n and body[i] in " \t\r\n,":
            i+=1
        if i>=n:
            break
        # read key
        m = re.match(r'([A-Za-z][A-Za-z0-9_\-]*)\s*=\s*', body[i:])
        if not m:
            # can't parse, skip to next comma
            j = body.find(",", i)
            if j==-1:
                break
            i=j+1
            continue
        k = m.group(1).lower()
        i += m.end()
        # read value
        if i>=n:
            break
        if body[i] == "{":
            depth=0
            start=i
            while i<n:
                if body[i]=="{":
                    depth+=1
                elif body[i]=="}":
                    depth-=1
                    if depth==0:
                        i+=1
                        break
                i+=1
            val = body[start:i].strip()
        elif body[i] == '"':
            i+=1
            start=i
            while i<n and body[i] != '"':
                # naive; ignores escaped quotes
                i+=1
            val = '"' + body[start:i] + '"'
            i+=1
        else:
            # bareword until comma
            start=i
            while i<n and body[i] not in ",\n\r":
                i+=1
            val = body[start:i].strip()
        fields[k] = _strip_outer_braces(val)
        # advance to next comma
        j = body.find(",", i)
        if j==-1:
            break
        i=j+1
    return fields

def parse_bib_file(bib_path: Path) -> List[BibEntry]:
    text = bib_path.read_text(encoding="utf-8", errors="ignore")
    entries: List[BibEntry] = []
    pos=0
    while True:
        m = _ENTRY_RE.search(text, pos)
        if not m:
            break
        entry_type = m.group("type").lower()
        key = m.group("key").strip()
        start = m.start()
        # find matching closing brace for the entry
        i = m.end()
        depth = 1
        while i < len(text) and depth>0:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        raw = text[start:i].strip()
        # body between first comma after key and the final closing brace
        body_start = text.find(",", m.end()-1) + 1
        body = text[body_start:i-1]
        fields = _parse_fields(body)
        entries.append(BibEntry(key=key, entry_type=entry_type, raw=raw, fields=fields))
        pos = i
    return entries
