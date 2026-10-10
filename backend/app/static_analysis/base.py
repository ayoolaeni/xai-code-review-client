"""Runner interface and the hardened subprocess helper (Sections 8.5.1 and 12.2).

SECURITY: never execute user code. Tools only *read* the snippet file; we never run the snippet itself.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.pipeline.types import StaticFinding, ToolRun

MEMORY_LIMIT_BYTES = int(1.5 * 1024**3)
CPU_LIMIT_SECONDS = 60


class Runner(Protocol):
    name: str
    languages: set[str]

    def available(self) -> bool: ...

    def version(self) -> str | None: ...

    def run(self, workdir: Path, filename: str, language: str) -> tuple[list[StaticFinding], ToolRun]: ...


@dataclass
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


class ToolTimeout(Exception):
    pass


def _limit_resources() -> None:  # pragma: no cover - runs in the child process on POSIX only
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS))


def run_tool(args: list[str], cwd: Path, timeout: int, limit_memory: bool = True) -> ProcessResult:
    """Run a static-analysis tool with an argument list (shell=False), a timeout and resource limits."""
    env = dict(os.environ)
    env.update(
        {
            "SEMGREP_SEND_METRICS": "off",
            "SEMGREP_ENABLE_VERSION_CHECK": "0",
            "NO_COLOR": "1",
            # PMD runs on the JVM, which cannot start under RLIMIT_AS; bound its heap instead.
            "PMD_JAVA_OPTS": "-Xmx512m",
        }
    )
    kwargs: dict = {}
    if os.name == "posix" and limit_memory:
        kwargs["preexec_fn"] = _limit_resources
    try:
        proc = subprocess.run(  # noqa: S603 - argument list built by the server, shell=False
            args,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(cwd),
            env=env,
            **kwargs,
        )
    except subprocess.TimeoutExpired as e:
        raise ToolTimeout(str(e)) from e
    return ProcessResult(proc.returncode, proc.stdout or "", proc.stderr or "")


def find_executable(name: str) -> str | None:
    """Look next to the running Python first (virtualenv scripts), then on PATH."""
    scripts = Path(sys.executable).parent
    for candidate in (scripts / name, scripts / f"{name}.exe"):
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name)


def first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def short_error(text: str, limit: int = 200) -> str:
    line = first_line(text)
    return line if len(line) <= limit else line[: limit - 1] + "…"
