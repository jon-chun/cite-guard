from __future__ import annotations
from typing import Any, Dict, List

def load_yaml(text: str) -> Dict[str, Any]:
    # Minimal YAML subset loader for this project's config.yaml.
    # Supports: key: scalar, nested dicts via indentation, inline lists,
    # and block-style list items (- "value").
    lines = text.splitlines()
    def strip_comment(ln: str) -> str:
        out = ln
        if "#" in out:
            out = out.split("#",1)[0]
        return out.rstrip()
    lines = [strip_comment(ln) for ln in lines]
    lines = [ln for ln in lines if ln.strip() != ""]
    root: Dict[str, Any] = {}
    # stack entries: (indent, container, parent_container, key_in_parent)
    stack: List[tuple[int, Any, Any, str]] = [(0, root, None, "")]
    for ln in lines:
        indent = len(ln) - len(ln.lstrip(" "))
        s = ln.strip()
        # adjust stack — never pop the root entry
        while len(stack) > 1 and indent < stack[-1][0]:
            stack.pop()
        container = stack[-1][1]
        if s.startswith("- "):
            item = s[2:].strip().strip('"').strip("'")
            if isinstance(container, dict):
                # An empty-value key (e.g. "blockers:") pushed a placeholder
                # dict; the first "- item" tells us it should be a list.
                new_list: List[Any] = []
                parent = stack[-1][2]
                key = stack[-1][3]
                if parent is not None:
                    parent[key] = new_list
                stack[-1] = (stack[-1][0], new_list, parent, key)
                container = new_list
            container.append(_parse_scalar(item))
            continue
        if ":" not in s:
            continue
        k, v = s.split(":",1)
        k=k.strip()
        v=v.strip()
        if v == "":
            new: Any = {}
            container[k]=new
            stack.append((indent+2, new, container, k))
        else:
            if v.startswith("[") and v.endswith("]"):
                inner=v[1:-1].strip()
                if inner=="":
                    val: Any=[]
                else:
                    parts=[p.strip() for p in inner.split(",")]
                    val=[_parse_scalar(p.strip().strip('"').strip("'")) for p in parts]
                container[k]=val
            else:
                container[k]=_parse_scalar(v.strip().strip('"').strip("'"))
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
