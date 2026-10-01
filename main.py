"""Entrypoint CLI."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from core.llm import LLMClient
from core.loop import run
from core.registry import ToolRegistry
from tools.bash_tool import BASH_SCHEMA, bash
from tools.file_tool import SCHEMAS as FILE_SCHEMAS
from tools.computer_tool import SCHEMAS as COMP_SCHEMAS
from sandbox.manager import DockerSandbox
import yaml


def build_registry(sandbox=None, computer_use_enabled=False):
    r = ToolRegistry()
    bash_fn = (lambda **kwargs: bash(**kwargs, sandbox=sandbox)) if sandbox else bash
    r.register("bash", "Chạy lệnh shell Ubuntu", BASH_SCHEMA, bash_fn)
    descs = {
        "read_file": "Đọc file",
        "write_file": "Tạo/ghi đè file",
        "edit_file": "Sửa 1 đoạn exact-match",
        "glob_files": "Tìm file theo pattern",
        "grep": "Tìm nội dung trong code",
        "screenshot": "Chụp desktop X11 trong VM (MSS)",
        "click": "Click theo tọa độ ảnh trong desktop X11 của VM",
        "type_text": "Gõ văn bản vào cửa sổ đang focus trong desktop X11 của VM",
        "press": "Nhấn phím hoặc tổ hợp phím trong desktop X11 của VM",
    }
    schemas = dict(FILE_SCHEMAS)
    if computer_use_enabled:
        schemas.update(COMP_SCHEMAS)

    for name, (schema, fn) in schemas.items():
        if sandbox and name in {"read_file", "write_file", "edit_file", "glob_files", "grep"}:
            fn = _workspace_tool(sandbox, fn)
        r.register(name, descs.get(name, name), schema, fn)
    return r


def _workspace_tool(sandbox, fn):
    """Keep host-side file tools inside the mounted workspace when sandboxed."""
    def call(**kwargs):
        for key in ("path", "pattern"):
            value = kwargs.get(key)
            if not value:
                continue
            candidate = Path(value)
            if key == "pattern" and (candidate.is_absolute() or ".." in candidate.parts):
                return "ERROR: path must stay inside the workspace"
            if key == "path":
                resolved = (sandbox.workspace / candidate).resolve()
                try:
                    relative = resolved.relative_to(sandbox.workspace)
                except ValueError:
                    return "ERROR: path must stay inside the workspace"
                if ".git" in relative.parts or any(part.startswith(".env") for part in relative.parts):
                    return "ERROR: access to private paths is blocked in sandbox mode"
                kwargs[key] = str(resolved)
        return fn(**kwargs)
    return call


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--computer-use", "--browser", dest="computer_use",
        action=argparse.BooleanOptionalAction, default=None,
        help="Bật/tắt computer-use X11; --browser vẫn là alias tương thích",
    )
    ap.add_argument("--task", required=True)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--max-steps", type=int, default=12)
    ap.add_argument(
        "--sandbox", action=argparse.BooleanOptionalAction, default=None,
        help="Chạy bash trong Docker; dùng --no-sandbox khi agent chạy trực tiếp trong VM",
    )
    a = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    config_path = Path(__file__).with_name("config.yaml")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    sandbox_config = config.get("sandbox", {})
    sandbox = None
    llm_config = config.get("llm", {})
    agent_config = config.get("agent", {})
    sandbox_enabled = sandbox_config.get("enabled", False) if a.sandbox is None else a.sandbox
    if sandbox_enabled:
        sandbox = DockerSandbox(sandbox_config.get("image", "agent-ubuntu:sandbox"))
    llm = LLMClient(
        model=os.getenv("LLM_MODEL") or llm_config.get("model", "~deepseek/deepseek-v4-flash-latest"),
        base_url=os.getenv("LLM_BASE_URL") or llm_config.get("base_url", "https://openrouter.ai/api/v1"),
        api_key=os.getenv("LLM_API_KEY", ""),
        temperature=float(os.getenv("LLM_TEMP", llm_config.get("temperature", 0.2))),
        mock=a.mock
    )
    max_steps = a.max_steps if a.max_steps != 12 else agent_config.get("max_step", 12)
    computer_use_config = config.get(
        "computer_use", config.get("browser", {})
    )
    computer_use_enabled = (
        computer_use_config.get("enabled", False)
        if a.computer_use is None
        else a.computer_use
    )
    registry = build_registry(sandbox, computer_use_enabled=computer_use_enabled)
    print(
        f"mode={'MOCK' if llm.mock else llm.model} "
        f"sandbox={'on' if sandbox else 'off'} "
        f"computer_use={'on' if computer_use_enabled else 'off'} "
        f"tools={registry.names()}"
    )
    result = run(a.task, llm, registry, max_steps=max_steps)
    print("\n=== FINAL ===\n" + result["final"])


if __name__ == "__main__":
    main()
