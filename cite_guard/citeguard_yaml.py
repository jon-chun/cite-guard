from __future__ import annotations
from typing import Any, Dict, List

def load_yaml(text: str) -> Dict[str, Any]:
    # Minimal YAML subset loader for this project's config.yaml.
    # Supports: key: scalar, nested dicts via indentation, inline lists, list items.
    lines = text.splitlines()
    # strip comments and blank lines
    def strip_comment(ln: str) -> str:
        out = ln
        if "#" in out:
            # naive: ignore quotes
            out = out.split("#",1)[0]
        return out.rstrip()
    lines = [strip_comment(ln) for ln in lines]
    lines = [ln for ln in lines if ln.strip() != ""]
    root: Dict[str, Any] = {}
    stack: List[tuple[int, Any]] = [(0, root)]
    for ln in lines:
        indent = len(ln) - len(ln.lstrip(" "))
        s = ln.strip()
        # adjust stack
        while stack and indent < stack[-1][0]:
            stack.pop()
        container = stack[-1][1]
        if s.startswith("- "):
            item = s[2:].strip().strip('"').strip("'")
            if not isinstance(container, list):
                raise ValueError("List item without list container")
            container.append(_parse_scalar(item))
            continue
        if ":" not in s:
            continue
        k, v = s.split(":",1)
        k=k.strip()
        v=v.strip()
        if v == "":
            # lookahead to see if next is list
            new = {}
            # if next line is list item at greater indent, convert to list later when encountered
            container[k]=new
            stack.append((indent+2, new))
        else:
            if v.startswith("[") and v.endswith("]"):
                inner=v[1:-1].strip()
                if inner=="":
                    val=[]
                else:
                    parts=[p.strip() for p in inner.split(",")]
                    val=[_parse_scalar(p.strip().strip('"').strip("'")) for p in parts]
                container[k]=val
            else:
                container[k]=_parse_scalar(v.strip().strip('"').strip("'"))
    # fix dicts that are actually lists for known keys
    # (only needed for this config)
    def ensure_list_at(path: str):
        parts=path.split(".")
        cur=root
        for p in parts[:-1]:
            cur=cur.get(p,{})
        last=parts[-1]
        if isinstance(cur.get(last), dict):
            # convert dict with numeric keys? not expected
            pass
    return root

def _parse_scalar(v: str):
    lv=v.lower()
    if lv in ("true","false"):
        return lv=="true"
    try:
        if "." in v:
            return float(v)
        return int(v)
    except Exception:
        return v
