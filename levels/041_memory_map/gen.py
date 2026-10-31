"""Level 41: the memory map must be what the BIOS reports, which depends on QEMU's
version and the memory size: the expected output comes from booting the level's
reference under the same conditions."""

import functools
import subprocess
import tempfile
from pathlib import Path


@functools.lru_cache(maxsize=None)
def truth(memory: str) -> bytes:
    from ring import qemu
    here = Path(__file__).parent
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["nasm", "-f", "bin", "-o", f"{d}/ref.img", str(here / "reference.asm")],
                       check=True)
        with qemu.Run(Path(f"{d}/ref.img").read_bytes(), profile="a20off", memory=memory) as run:
            run.wait("halt")
            return run.serial()


def case(name, memory, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"bios": "a20off", "memory": memory},
            "expect": {"check": True, "memory": memory}}


def check(test, run, regs, screen, serial):
    want = truth(test.expect["memory"])
    out = []
    if serial != want:
        w, g = want.decode().splitlines(), serial.decode("latin-1").splitlines()
        for k, line in enumerate(w):
            if k >= len(g) or g[k] != line:
                out.append(f"serial line {k + 1}: expected {line!r}, got "
                           + (repr(g[k]) if k < len(g) else "nothing"))
                break
        else:
            out.append(f"serial: {len(g) - len(w)} line(s) too many: {g[len(w)]!r}")
        out.append("the whole map, from this BIOS:\n" + "\n".join("    " + l for l in w))
    if regs is not None and not regs.a20:
        out.append("A20 is still off when the program halts")
    return out


def fixed_tests(ctx):
    return [case("32 MiB of memory", "32M")]


def generate(rng, count, ctx):
    return [case(f"{m} of memory", m, True) for m in ["48M", "200M"][:count]]


def audit(build):
    from ring.checks import disassemble
    ins = disassemble(build)
    return [("asks the BIOS for the map (int 0x15)", any(mn == "int" and ops == "0x15" for _, mn, ops in ins), "")]
