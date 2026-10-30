"""The game's tiny /bin: small static programs (written in NASM, in ring/bin/)
that levels about processes can execve inside the emulated kernel."""

from __future__ import annotations

import functools
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path(__file__).parent / "bin"


@functools.cache
def programs() -> dict[str, bytes]:
    """name -> ELF image, assembled once per run."""
    out = {}
    with tempfile.TemporaryDirectory(prefix="ring-userland-") as tmp:
        for src in sorted(SOURCE.glob("*.asm")):
            obj, exe = Path(tmp) / f"{src.stem}.o", Path(tmp) / src.stem
            subprocess.run(["nasm", "-f", "elf64", "-I", f"{SOURCE}/", "-o", obj, src],
                           check=True, capture_output=True)
            subprocess.run(["ld", "-o", exe, obj], check=True, capture_output=True)
            out[src.stem] = exe.read_bytes()
    return out


def install_userland(kernel) -> None:
    for name, image in programs().items():
        kernel.make_file(f"/bin/{name}", image, mode=0o755, uid=0)
