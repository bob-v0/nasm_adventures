"""Native runner: levels that need the real C library (Arc IV's libc levels) are
linked with gcc and run as ordinary processes, with time and memory limits.

There is no reverse debugging here; players use gdb in the Terminal tab. On a
non-x86 host the program runs under qemu-x86_64 user-mode emulation if it's installed.
"""

from __future__ import annotations

import errno
import platform
import resource
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .build import BuildError

TIMEOUT_S = 10
MEMORY_LIMIT = 512 << 20


def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT_S, TIMEOUT_S))
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def runner_prefix() -> list[str]:
    if platform.machine() in ("x86_64", "AMD64"):
        return []
    if shutil.which("qemu-x86_64"):
        return ["qemu-x86_64"]
    raise BuildError("this level runs x86-64 programs natively, and this machine isn't x86-64. "
                     "Install qemu-user (qemu-x86_64) or use an x86-64 host.")


@dataclass
class NativeResult:
    stdout: bytes
    stderr: bytes
    exit_code: int | None
    signal: int | None
    timed_out: bool
    error: str = ""          # the kernel refused to start it (execve failed)


def run(exe: Path, stdin: bytes, args: list[str] = ()) -> NativeResult:
    try:
        p = subprocess.run([*runner_prefix(), str(exe), *args], input=stdin, capture_output=True,
                           timeout=TIMEOUT_S, preexec_fn=_limits, cwd=exe.parent,
                           env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
    except subprocess.TimeoutExpired as e:
        return NativeResult(e.stdout or b"", e.stderr or b"", None, None, True)
    except OSError as e:                # e.g. ENOEXEC: not a valid executable
        return NativeResult(b"", b"", None, None, False,
                            f"the kernel refused to run it: execve failed with "
                            f"{errno.errorcode.get(e.errno, e.errno)} ({e.strerror})")
    sig = -p.returncode if p.returncode < 0 else None
    return NativeResult(p.stdout, p.stderr, None if sig else p.returncode, sig, False)
