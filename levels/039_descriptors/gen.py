"""Level 39: the GDT the player loads, field by field."""


def decode(d: bytes) -> dict:
    lo, hi = int.from_bytes(d[:4], "little"), int.from_bytes(d[4:], "little")
    access = hi >> 8 & 0xFF
    flags = hi >> 20 & 0xF
    return {"base": (lo >> 16) | (hi & 0xFF) << 16 | (hi >> 24) << 24,
            "limit": (lo & 0xFFFF) | (hi >> 16 & 0xF) << 16,
            "access": access, "P": access >> 7, "DPL": access >> 5 & 3, "S": access >> 4 & 1,
            "type": access & 0xF, "G": flags >> 3, "D": flags >> 2 & 1, "L": flags >> 1 & 1}


def check_flat(raw: bytes, base: int, limit: int) -> list[str]:
    """Problems with a GDT of null, flat code (0x08), flat data (0x10)."""
    if limit != 3 * 8 - 1:
        return [f"the GDT's limit is {limit:#x}: three 8-byte entries make a limit of 0x17 "
                "(the size minus one)"]
    if raw[:8] != bytes(8):
        return ["entry 0 (selector 0x00) must be all zeros: the null descriptor"]
    out = []
    for sel, kind, want_type in ((0x08, "code", 0xA), (0x10, "data", 0x2)):
        d = decode(raw[sel:sel + 8])
        name = f"entry {sel // 8} (selector {sel:#04x}, {kind})"
        if d["base"] != 0:
            out.append(f"{name}: base {d['base']:#x}, should be 0 (flat: the segment starts at 0)")
        elif not (d["limit"] == 0xFFFFF and d["G"] == 1):
            out.append(f"{name}: limit {d['limit']:#x} with G = {d['G']}: a 4 GiB segment is limit "
                       "0xFFFFF with G = 1 (in 4 KiB units)")
        elif d["P"] != 1:
            out.append(f"{name}: not present (P = 0)")
        elif d["S"] != 1:
            out.append(f"{name}: S = 0 makes it a system descriptor; code and data have S = 1")
        elif d["DPL"] != 0:
            out.append(f"{name}: DPL {d['DPL']}, should be 0 (the kernel's)")
        elif d["type"] != want_type:
            out.append(f"{name}: type {d['type']:#x}, should be {want_type:#x} "
                       + ("(code: execute + read)" if kind == "code" else "(data: read + write)"))
        elif d["D"] != 1 or d["L"] != 0:
            out.append(f"{name}: flags D = {d['D']}, L = {d['L']}: 32-bit is D = 1, L = 0")
    return out


def check(test, run, regs, screen, serial):
    base, limit = regs.values.get("gdt_base"), regs.values.get("gdt_limit")
    if base is None:
        return ["couldn't read the GDT register"]
    if base == 0 and limit in (0, 0xFFFF):
        return ["no GDT loaded: lgdt [pointer], where the pointer is dw limit / dd base"]
    return check_flat(run.read(base, 24), base, limit)


def fixed_tests(ctx):
    return [{"name": "the GDT", "expect": {"check": True}}]
