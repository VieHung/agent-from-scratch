"""Tool bash an toàn cho Phase 1."""
import subprocess
from sandbox.errors import SandboxError

BLOCKED = ["rm -rf /", "mkfs", "dd if=", ":(){", "shutdown", "reboot", "chmod -R 777 /"]


def bash(command: str, timeout: int = 30, workdir: str = ".", sandbox=None) -> str:
    for b in BLOCKED:
        if b in command:
            return f"BLOCKED: lệnh chứa pattern nguy hiểm '{b}'"
    if sandbox is not None:
        try:
            return sandbox.run(command, timeout=timeout, workdir=workdir)
        except SandboxError as exc:
            return f"ERROR: {exc}"            
    try:
        p = subprocess.run(
            command, shell=True, cwd=workdir or ".",
            capture_output=True, text=True, timeout=int(timeout),
        )
        out = (p.stdout or "") + (("\nSTDERR:\n" + p.stderr) if p.stderr else "")
        out = out.strip() or f"(exit {p.returncode}, no output)"
        if len(out) > 4000:
            out = out[:4000] + "\n...[truncated]"
        return f"[exit {p.returncode}] {out}"
    except subprocess.TimeoutExpired:
        return f"TIMEOUT sau {timeout}s: {command}"
    except Exception as e:
        return f"ERROR: {e}"


BASH_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "Lệnh shell Ubuntu"},
        "timeout": {"type": "integer", "default": 30},
        "workdir": {"type": "string", "default": "."},
    },
    "required": ["command"],
}
