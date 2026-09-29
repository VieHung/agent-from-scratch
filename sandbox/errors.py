"""Typed errors raised by the Docker sandbox."""


class SandboxError(RuntimeError):
    """Base class for sandbox-related failures."""


class WorkspacePathError(SandboxError):
    """The requested working directory is outside the mounted workspace."""


class DockerUnavailableError(SandboxError):
    """The Docker CLI or daemon could not be reached."""


class ImageBuildError(SandboxError):
    """The sandbox Docker image could not be built."""


class SandboxTimeoutError(SandboxError):
    """A sandbox command exceeded its time limit."""


class SandboxExecutionError(SandboxError):
    """Docker could not create or start the sandbox container."""
