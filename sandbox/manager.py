"""Minimal Docker executor for Phase 2."""
from pathlib import Path
import subprocess

from .errors import (
    DockerUnavailableError,
    ImageBuildError,
    SandboxError,
    SandboxExecutionError,
    SandboxTimeoutError,
    WorkspacePathError,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCKER_UNAVAILABLE_HINTS = (
    "permission denied while trying to connect",
    "cannot connect to the docker daemon",
    "error during connect",
    "is the docker daemon running",
)


def _docker_is_unavailable(message):
    message = message.lower()
    return any(hint in message for hint in DOCKER_UNAVAILABLE_HINTS)


def _docker_error(result):
    return (result.stderr or result.stdout or "Docker command failed").strip()


class DockerSandbox:
    def __init__(self, image="agent-ubuntu:sandbox"):
        self.image = image
        self.workspace = Path.cwd().resolve()

    def _ensure_image(self):
        try:
            inspect = subprocess.run(
                ["docker", "image", "inspect", self.image],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise DockerUnavailableError(f"Không chạy được Docker CLI: {exc}") from exc

        if inspect.returncode == 0:
            return

        inspect_error = _docker_error(inspect)
        if _docker_is_unavailable(inspect_error):
            raise DockerUnavailableError(inspect_error)

        try:
            build = subprocess.run(
                ["docker", "build", "-t", self.image,
                 "-f", "sandbox/Dockerfile", "."],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise DockerUnavailableError(f"Không chạy được Docker CLI: {exc}") from exc

        if build.returncode != 0:
            detail = _docker_error(build)
            if _docker_is_unavailable(detail):
                raise DockerUnavailableError(detail)
            raise ImageBuildError(detail)

    def run(self, command, timeout=30, workdir="."):
        try:
            timeout_seconds = int(timeout)
        except (TypeError, ValueError, OverflowError) as exc:
            raise SandboxError(f"timeout phải là số nguyên: {timeout!r}") from exc

        try:
            host_cwd = (self.workspace / (workdir or ".")).resolve()
            relative_cwd = host_cwd.relative_to(self.workspace)
        except (TypeError, ValueError, OSError, RuntimeError) as exc:
            raise WorkspacePathError(
                f"workdir không hợp lệ hoặc nằm ngoài workspace {self.workspace}: {workdir!r}"
            ) from exc

        container_cwd = "/workspace/" + relative_cwd.as_posix()
        self._ensure_image()

        args = ["docker", "run", "--rm", "--network", "none",
                "--read-only", "--cpus", "1", "--memory", "512m",
                "--pids-limit", "128", "--user", "1000:1000",
                "--mount", f"type=bind,src={self.workspace},dst=/workspace",
                "--tmpfs", "/workspace/.git:rw,nosuid,nodev,noexec,size=1m",
                "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m"]
        for secret in self.workspace.glob(".env*"):
            if secret.is_file():
                args += ["--mount", f"type=bind,src=/dev/null,dst=/workspace/{secret.name},readonly"]
        args += ["--workdir", container_cwd, "--env", "HOME=/tmp",
                 self.image, "bash", "-lc", command]

        try:
            result = subprocess.run(
                args,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SandboxTimeoutError(
                f"Lệnh vượt quá giới hạn {timeout_seconds}s"
            ) from exc
        except OSError as exc:
            raise DockerUnavailableError(f"Không chạy được Docker CLI: {exc}") from exc

        detail = _docker_error(result)
        if result.returncode == 125:
            if _docker_is_unavailable(detail):
                raise DockerUnavailableError(detail)
            raise SandboxExecutionError(detail)

        output = result.stdout or ""
        if result.stderr:
            output += "\nSTDERR:\n" + result.stderr
        output = output.strip() or f"(exit {result.returncode}, no output)"
        if len(output) > 4000:
            output = output[:4000] + "\n...[truncated]"
        return f"[exit {result.returncode}] {output}"
