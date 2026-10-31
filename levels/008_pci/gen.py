"""Level 8: the kernel lists bus 0's PCI devices and their BARs. Where the firmware put
each BAR depends on the QEMU version: what each machine looks like is asked of the
level's reference kernel (and it agrees with QEMU's own `info pci`)."""

import functools

Q35 = ["-machine", "q35"]
MACHINES = {
    "the bare chipset": Q35,
    "a network card": Q35 + ["-device", "e1000"],
    "a 64-bit BAR": Q35 + ["-device", "virtio-rng-pci", "-device", "pci-testdev"],
    "four more": Q35 + ["-device", "rtl8139", "-device", "e1000", "-device", "virtio-rng-pci",
                        "-device", "pci-testdev"],
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
    return [case("the bare chipset"), case("a network card")]


def generate(rng, count, ctx):
    return [case(n, True) for n in list(MACHINES)[2:]]
