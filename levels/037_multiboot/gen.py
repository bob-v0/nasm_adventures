"""Level 37: the kernel reports what the multiboot loader told it."""


import functools


@functools.lru_cache(maxsize=None)
def memory_line(memory_mib: int) -> str:
    """What QEMU's loader reports depends on the BIOS (it keeps some memory at the top):
    ask it, by booting the level's reference kernel."""
    import tempfile
    from pathlib import Path
    from ring import qemu
    with tempfile.TemporaryDirectory() as d:
        kernel = qemu.link_kernel(Path(__file__).parent / "reference.asm", Path(d))
        with qemu.Run(b"", kernel=kernel, memory=f"{memory_mib}M") as run:
            run.wait("halt")
            return next(l for l in run.serial().decode().splitlines() if l.startswith("memory: "))


def case(name, cmdline, memory_mib, modules, hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"cmdline": cmdline, "memory": f"{memory_mib}M",
                       "modules": [m.encode().hex() for m in modules]},
            "expect": {"check": True, "cmdline": cmdline, "memory_mib": memory_mib,
                       "modules": modules}}


def check(test, run, regs, screen, serial):
    from ring.checks import _compare_text
    e = test.expect
    want = (f"booted by a multiboot loader\r\ncommand line: kernel.elf {e['cmdline']}\r\n"
            f"{memory_line(e['memory_mib'])}\r\nmodules: {len(e['modules'])}\r\n"
            + "".join(e["modules"]))
    return [] if serial == want.encode() else [_compare_text("serial port", want.encode(), serial)]


def fixed_tests(ctx):
    return [case("one module", "verbose=1 root=/dev/ring0", 32, ["The game's first module.\r\n"])]


def generate(rng, count, ctx):
    words = ["quiet", "debug", "init=/bin/ring", "console=ttyS0", "level=37", "acpi=off"]
    out = [case("no modules", "", 64, [], True)]
    for i in range(count):
        mods = [f"Module {k}: " + " ".join(rng.choice(words) for _ in range(3)) + "\r\n"
                for k in range(rng.randrange(1, 4))]
        out.append(case(f"random {i}", " ".join(rng.sample(words, 3)), rng.choice([16, 48, 128]), mods, True))
    return out
