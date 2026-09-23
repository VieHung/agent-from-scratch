"""Smoke test offline: ReAct loop + tools, không cần API key."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.loop import run
from core.llm import LLMClient
from core.registry import ToolRegistry
from tools.bash_tool import BASH_SCHEMA, bash
from tools.file_tool import SCHEMAS


def test_registry_blocks_rm_rf():
    r = ToolRegistry()
    r.register("bash", "shell", BASH_SCHEMA, bash)
    out = r.execute("bash", {"command": "rm -rf /"})
    assert "BLOCKED" in out, out
    print("PASS block rm-rf")


def test_mock_loop_creates_file():
    with tempfile.TemporaryDirectory() as td:
        cwd = os.getcwd()
        os.chdir(td)
        try:
            r = ToolRegistry()
            r.register("bash", "shell", BASH_SCHEMA, bash)
            for name, (schema, fn) in SCHEMAS.items():
                r.register(name, name, schema, fn)
            llm = LLMClient(mock=True)
            res = run("tạo file hello.py", llm, r, max_steps=4, verbose=False)
            assert os.path.exists("hello.py"), "mock loop chưa tạo hello.py"
            print("PASS mock loop -> hello.py:", res["final"][:120])
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    test_registry_blocks_rm_rf()
    test_mock_loop_creates_file()
    print("ALL SMOKE PASS")
