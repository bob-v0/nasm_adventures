"""Level 25: the kernel must end in 64-bit mode, running at its higher-half address, and
say where it is."""

import re

HIGH = 0xFFFFFFFF80000000


def case(name, cpu, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"cpu": cpu},
            "expect": {"check": True, "timeout": 10}}


def check(test, run, regs, screen, serial):
    if regs is None:
        return []
    cr0, cr4, efer = regs.values.get("cr0", 0), regs.values.get("cr4", 0), regs.values.get("efer", 0)
    if not cr0 & 1 << 31:
        return ["paging is off at the halt (CR0 bit 31, PG): long mode starts when paging goes on"]
    if not efer & 1 << 10:
        if not cr4 & 1 << 5:
            return ["paging is on, but without PAE (CR4 bit 5): that's 32-bit paging, not long mode"]
        return ["paging is on, but long mode isn't active (EFER.LMA): set EFER.LME (bit 8) "
                "before turning on paging"]
    if not regs.long_mode:
        return ["long mode is active, but the code still runs as 32-bit (compatibility mode): far "
                "jump to a 64-bit code segment, a GDT entry with the L bit (0x00209A0000000000)"]
    rip = regs.values.get("rip", 0)
    if rip < HIGH:
        return [f"64-bit mode, but at {rip:#x}: the kernel should end up running in the higher "
                f"half, at {HIGH:#x} + its address (`mov rax, HIGH + label`, `jmp rax`)"]
    m = re.fullmatch(rb"hello from long mode, at 0x([0-9a-f]{16})\r\n", serial)
    if not m:
        return [f"the serial port should say `hello from long mode, at 0x` and 16 lowercase hex "
                f"digits, then a new line; it says {serial[:80]!r}"]
    at = int(m.group(1), 16)
    end = run.symbols.get("kernel_end", 0x200000)
    if not (HIGH + 0x100000 <= at < HIGH + end):
        return [f"it says it's at {at:#x}, which isn't in the kernel's higher-half code "
                f"({HIGH + 0x100000:#x} – {HIGH + end:#x}): print the address it runs at "
                "(`lea rax, [rel label]`)"]
    return []


def fixed_tests(ctx):
    return [case("qemu64", "qemu64")]


def generate(rng, count, ctx):
    return [case(c, c, True) for c in ("Haswell", "EPYC", "Conroe")]
