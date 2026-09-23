"""Entrypoint CLI."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from core.llm import LLMClient
from core.loop import run
from core.registry import ToolRegistry
from tools.bash_tool import BASH_SCHEMA, bash
from tools.file_tool import SCHEMAS as FILE_SCHEMAS
from tools.computer_tool import SCHEMAS as COMP_SCHEMAS


def build_registry():
    r = ToolRegistry()
    r.register("bash", "Chạy lệnh shell Ubuntu", BASH_SCHEMA, bash)
    descs = {
        "read_file": "Đọc file",
        "write_file": "Tạo/ghi đè file",
        "edit_file": "Sửa 1 đoạn exact-match",
        "glob_files": "Tìm file theo pattern",
        "grep": "Tìm nội dung trong code",
        "screenshot": "Chụp màn hình (stub Phase 3)",
        "click": "Click chuột (stub Phase 3)",
        "type_text": "Gõ phím (stub Phase 3)",
    }
    for name, (schema, fn) in {**FILE_SCHEMAS, **COMP_SCHEMAS}.items():
        r.register(name, descs.get(name, name), schema, fn)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--max-steps", type=int, default=12)
    a = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    llm = LLMClient(mock=a.mock)
    print(f"mode={'MOCK' if llm.mock else llm.model} tools={build_registry().names()}")
    result = run(a.task, llm, build_registry(), max_steps=a.max_steps)
    print("\n=== FINAL ===\n" + result["final"])


if __name__ == "__main__":
    main()
