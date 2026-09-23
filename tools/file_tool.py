"""Tools file cho coding agent: read/write/edit/glob/grep."""
import glob as globlib
import os
import re


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = f.read()
    return data[:8000] + ("\n...[truncated]" if len(data) > 8000 else "")


def write_file(path: str, content: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"WROTE {path} ({len(content)} chars)"


def edit_file(path: str, oldString: str, newString: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        data = f.read()
    if oldString not in data:
        return "ERROR: oldString not found"
    data = data.replace(oldString, newString, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    return f"EDITED {path}"


def glob_files(pattern: str) -> str:
    hits = globlib.glob(pattern, recursive=True)[:50]
    return "\n".join(hits) or "(no match)"


def grep(pattern: str, include: str = "*.py", path: str = ".") -> str:
    rx = re.compile(pattern)
    out = []
    for root, _, files in os.walk(path):
        for fn in files:
            if not globlib.fnmatch.fnmatch(fn, include):
                continue
            fp = os.path.join(root, fn)
            try:
                with open(fp, encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if rx.search(line):
                            out.append(f"{fp}:{i}:{line.strip()[:200]}")
                            if len(out) >= 50:
                                return "\n".join(out)
            except Exception:
                continue
    return "\n".join(out) or "(no match)"


SCHEMAS = {
    "read_file": ({"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}, read_file),
    "write_file": ({"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}, write_file),
    "edit_file": ({"type": "object", "properties": {"path": {"type": "string"}, "oldString": {"type": "string"}, "newString": {"type": "string"}}, "required": ["path", "oldString", "newString"]}, edit_file),
    "glob_files": ({"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}, glob_files),
    "grep": ({"type": "object", "properties": {"pattern": {"type": "string"}, "include": {"type": "string", "default": "*.py"}, "path": {"type": "string", "default": "."}}, "required": ["pattern"]}, grep),
}
