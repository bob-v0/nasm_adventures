"""Level 28: the kernel reports what the CPU says about itself. The CPU is a different
QEMU model in each test; what each model reports is asked of the level's reference kernel
(it depends on the QEMU version)."""

import functools

FIXED = ["qemu64", "qemu32"]
HIDDEN = ["Haswell", "EPYC", "Skylake-Server", "phenom", "qemu64,-nx", "Conroe", "pentium3", "486",
          # SSE2 (leaf 1, edx bit 26) but no extended leaves: asked for 0x80000001, it
          # answers with leaf 1, whose bit 26 isn't "1 GiB pages"
          "qemu64,level=1,xlevel=0x80000000"]


@functools.lru_cache(maxsize=None)
def report(cpu: str) -> str:
    import tempfile
    from pathlib import Path
    from ring import qemu
    with tempfile.TemporaryDirectory() as d:
        kernel = qemu.link_kernel(Path(__file__).parent / "reference.asm", Path(d), elf64=True)
        with qemu.Run(b"", kernel=kernel, extra_args=["-cpu", cpu]) as run:
            run.wait("halt")
            return run.serial().decode()


def case(name, cpu, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"cpu": cpu},
            "expect": {"check": True, "cpu": cpu}}


def check(test, run, regs, screen, serial):
    from ring.checks import _compare_text
    want = report(test.expect["cpu"]).encode()
    return [] if serial == want else [_compare_text("serial port", want, serial)]


def fixed_tests(ctx):
    return [case(f"cpu {c}", c) for c in FIXED]


def generate(rng, count, ctx):
    return [case(f"cpu {c}", c, True) for c in HIDDEN]
