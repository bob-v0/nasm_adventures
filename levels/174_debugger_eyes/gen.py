import random
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

M = (1 << 64) - 1


def seeds(ctx):
    rng = random.Random(f"vault-{ctx.seed}")
    return [rng.getrandbits(64) for _ in range(3)]


def key(ctx):
    """Python model of vault.asm."""
    a, b, c = seeds(ctx)
    r = a ^ b
    r = ((r << 13) | (r >> 51)) & M
    r = (r + c) & M
    r = (r * 0x9E3779B97F4A7C15) & M
    return r ^ (r >> 29)


def build_vault(level, ctx, out: Path, strip: bool = True) -> None:
    a, b, c = seeds(ctx)
    with tempfile.TemporaryDirectory() as tmp:
        obj = Path(tmp) / "vault.o"
        subprocess.run(["nasm", "-f", "elf64", f"-DSEED_A={a:#x}", f"-DSEED_B={b:#x}",
                        f"-DSEED_C={c:#x}", "-o", str(obj), str(level.path / "vault.asm")],
                       check=True)
        subprocess.run(["ld", *(["-s"] if strip else []), "-o", str(out), str(obj)], check=True)
    out.chmod(out.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def prepare(level, workdir: Path, ctx):
    out = workdir / "vault"
    build_vault(level, ctx, out)
    print(f"  built {out}  (your personal vault; its key is different for every player)")


def fixed_tests(ctx):
    k = key(ctx)
    return [{"name": "the vault key", "expect": {"stdout_hex": k.to_bytes(8, "little").hex(),
                                                  "exit": 0}}]
