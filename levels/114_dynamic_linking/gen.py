AGREE = "the GOT and dlsym agree on puts\n"
LIBC = {"strlen", "printf", "puts", "dlsym"}


def case(name, args, hidden=False):
    out = "".join(f"{a}: {len(a.encode())}\n" for a in args) + AGREE
    return {"name": name, "hidden": hidden, "expect": {"args": args, "stdout": out, "exit": 0}}


def fixed_tests(ctx):
    return [case("two words", ["ring", "zero"]), case("no arguments", [])]


def generate(rng, count, ctx):
    import string
    return [case(f"random {i}", ["".join(rng.choice(string.ascii_letters) for _ in range(rng.randrange(1, 30)))
                                 for _ in range(rng.randrange(1, 6))], True) for i in range(count)]


def audit(build):
    """Every use of a libc function must go through its GOT slot: no PLT, anywhere."""
    from elftools.elf.elffile import ELFFile
    from elftools.elf.relocation import RelocationSection
    via_plt, via_got = set(), set()
    with open(build.player_object, "rb") as fh:
        elf = ELFFile(fh)
        for sec in elf.iter_sections():
            if not isinstance(sec, RelocationSection):
                continue
            symtab = elf.get_section(sec["sh_link"])
            for rel in sec.iter_relocations():
                sym = symtab.get_symbol(rel["r_info_sym"])
                if sym["st_shndx"] != "SHN_UNDEF":
                    continue          # the program's own labels
                kind = rel["r_info_type"]
                if kind in (9, 41, 42):            # GOTPCREL, GOTPCRELX, REX_GOTPCRELX
                    via_got.add(sym.name)
                else:                              # PLT32, PC32, 64, ...
                    via_plt.add(sym.name)
    missing = sorted(LIBC - via_got)
    return [("no PLT: every libc reference goes through the GOT", not via_plt,
             f"not through the GOT: {', '.join(sorted(via_plt))}" if via_plt else ""),
            ("uses the GOT slots of strlen, printf, puts and dlsym", not missing,
             f"missing: {', '.join(missing)}" if missing else "")]
