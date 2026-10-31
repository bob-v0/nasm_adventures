"""Level 26: the game walks the kernel's page tables (eax = the PML4's address at the
halt), the way the CPU will in level 25, for addresses inside and outside each region."""

GIB = 1 << 30
HIGH = 0xFFFFFFFF80000000          # the kernel's higher half (the top 2 GiB)
DIRECT = 0xFFFF800000000000        # the direct map, no-execute
ADDR_MASK = 0x000FFFFFFFFFF000     # bits 12-51: the next table, or the page
RESERVED = 0x000FFF0000000000      # bits 40-51: above this CPU's 40 physical address bits
NAMES = ["PML4", "PDPT", "PD", "PT"]


def walk(read, cr3, va):
    """(physical address or None, writable, user, nx, path, problem)"""
    table = cr3 & ADDR_MASK
    idx = [(va >> 39) & 511, (va >> 30) & 511, (va >> 21) & 511, (va >> 12) & 511]
    writable, user, nx, path = True, True, False, []
    for level in range(4):
        path.append(f"{NAMES[level]}[{idx[level]}]")
        e = int.from_bytes(read(table + idx[level] * 8), "little")
        where = " → ".join(path)
        if not e & 1:
            return None, writable, user, nx, where, ""
        if e & RESERVED:
            return None, writable, user, nx, where, (
                f"{where} = {e:#018x} has bits set above bit 39: this CPU has 40 physical "
                "address bits, and the rest are reserved (a page fault)")
        writable &= bool(e & 2)
        user &= bool(e & 4)
        nx |= bool(e >> 63)
        ps = e & (1 << 7)
        if level == 0 and ps:
            return None, writable, user, nx, where, f"{where}: bit 7 (PS) is reserved in a PML4 entry"
        if level == 1 and ps:
            return None, writable, user, nx, where, (
                f"{where} is a 1 GiB page (PS): this CPU (qemu64) doesn't have them (level 28's "
                "`1g pages: no`): use 2 MiB pages, in a PD")
        if level == 2 and ps:
            if e & 0x1FE000:
                return None, writable, user, nx, where, (
                    f"{where} = {e:#018x}: a 2 MiB page must start at a multiple of 2 MiB "
                    "(bits 13-20 are reserved)")
            return (e & ADDR_MASK & ~0x1FFFFF) | (va & 0x1FFFFF), writable, user, nx, where, ""
        if level == 3:
            return (e & ADDR_MASK) | (va & 0xFFF), writable, user, nx, where, ""
        table = e & ADDR_MASK
    raise AssertionError


def samples(rng):
    """(virtual address, expected physical or None, expected nx)"""
    out = [(0, None, False), (0xFFF, None, False), (0x1000, 0x1000, False),
           (0xB8000, 0xB8000, False), (0x100000, 0x100000, False), (0x1FFFFF, 0x1FFFFF, False),
           (0x200000, 0x200000, False), (GIB - 8, GIB - 8, False), (GIB, None, False),
           (0x80000000, None, False), (0x8000000000, None, False), (0x00007FFFFFFFF000, None, False),
           (HIGH + 0x100000, 0x100000, False), (HIGH + 0x200000, 0x200000, False),
           (HIGH + GIB - 8, GIB - 8, False), (HIGH + GIB, None, False),
           (DIRECT + 0x1000, 0x1000, True), (DIRECT + 0x300000, 0x300000, True),
           (DIRECT + GIB - 8, GIB - 8, True), (DIRECT + GIB, None, False),
           (0xFFFF808000000000, None, False)]
    for _ in range(12):
        x = rng.randrange(0x1000, GIB) & ~7
        out += [(x, x, False), (HIGH + x, x, False), (DIRECT + x, x, True)]
    out.append((rng.randrange(GIB, 1 << 39) & ~7, None, False))
    return out


def case(name, seed, hidden=False):
    return {"name": name, "hidden": hidden,
            "expect": {"check": True, "seed": seed, "timeout": 10}}


def check(test, run, regs, screen, serial):
    import random
    if regs is None:
        return []
    cr3 = regs["eax"]
    if cr3 & 0xFFF:
        return [f"eax = {cr3:#x}: the PML4's address must be a multiple of 4096 (its low 12 "
                "bits are flags in CR3)"]
    if not 0x100000 <= cr3 < 64 << 20:
        return [f"eax = {cr3:#x}: that's not a PML4 in your kernel's memory (end with eax = "
                "the PML4's address)"]
    cache = {}

    def read(addr):
        page = addr & ~0xFFF
        if page not in cache:
            cache[page] = run.read(page, 4096)
        return cache[page][addr & 0xFFF:(addr & 0xFFF) + 8]

    for va, want, want_nx in samples(random.Random(test.expect["seed"])):
        phys, w, u, nx, where, problem = walk(read, cr3, va)
        if problem:
            return [f"at {va:#018x}: {problem}"]
        if want is None:
            if phys is not None:
                return [f"{va:#018x} should not be mapped, but it is ({where} → {phys:#x})"]
            continue
        if phys is None:
            return [f"{va:#018x} should map to {want:#x}, but {where} isn't present"]
        if phys != want:
            return [f"{va:#018x} maps to {phys:#x} ({where}); expected {want:#x}"]
        if not w:
            return [f"{va:#018x} isn't writable: bit 1 (W) must be set at every level ({where})"]
        if u:
            return [f"{va:#018x} is reachable from user mode: bit 2 (U) is set at every level "
                    f"({where}); kernel memory must not be"]
        if nx != want_nx:
            return [f"{va:#018x} should be no-execute (bit 63 at some level), but isn't ({where})"
                    if want_nx else
                    f"{va:#018x} should be executable, but bit 63 (NX) is set on the way ({where})"]
    return []


def fixed_tests(ctx):
    return [case("the three regions", 1)]


def generate(rng, count, ctx):
    return [case(f"random addresses {i}", rng.randrange(1 << 30), True) for i in range(count)]
