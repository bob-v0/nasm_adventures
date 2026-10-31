"""Level 9: the kernel reports what ACPI's MADT says about the machine. The machines vary
(CPUs, sockets and cores, CPUs that aren't there yet); what each one's tables say is asked
of the level's reference kernel (it depends on the QEMU version)."""

import functools

MACHINES = {
    "one CPU": ["-smp", "1"],
    "four CPUs": ["-smp", "4"],
    "two sockets of three cores": ["-smp", "6,sockets=2,cores=3"],
    "room for twelve, eight present": ["-smp", "8,maxcpus=12"],
    "q35, two CPUs": ["-machine", "q35", "-smp", "2"],
}


@functools.lru_cache(maxsize=None)
def report(name: str) -> str:
    import tempfile
    from pathlib import Path
    from ring import qemu
    with tempfile.TemporaryDirectory() as d:
        kernel = qemu.link_kernel(Path(__file__).parent / "reference.asm", Path(d), elf64=True)
        with qemu.Run(b"", kernel=kernel, extra_args=MACHINES[name]) as run:
            run.wait("halt")
            return run.serial().decode()


def case(name, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"qemu_args": MACHINES[name]},
            "expect": {"check": True, "machine": name}}


def check(test, run, regs, screen, serial):
    from ring.checks import _compare_text
    want = report(test.expect["machine"]).encode()
    return [] if serial == want else [_compare_text("serial port", want, serial)]


def fixed_tests(ctx):
    return [case("one CPU"), case("four CPUs")]


def generate(rng, count, ctx):
    return [case(n, True) for n in list(MACHINES)[2:]]
