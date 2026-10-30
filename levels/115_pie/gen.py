DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def case(name, digits, hidden=False):
    out = "".join(f"{DAYS[d]}\n  {'rest' if d >= 5 else 'work'}\n" for d in digits)
    return {"name": name, "hidden": hidden,
            "expect": {"args": [str(d) for d in digits], "stdout": out, "exit": 0}}


def fixed_tests(ctx):
    return [case("Monday", [0]), case("a weekend", [5, 6]), case("no arguments", [])]


def generate(rng, count, ctx):
    return [case(f"random {i}", [rng.randrange(7) for _ in range(rng.randrange(1, 8))], True)
            for i in range(count)]


def audit(build):
    """The ELF itself: a PIE, with no text relocations."""
    from elftools.elf.elffile import ELFFile
    with open(build.elf, "rb") as fh:
        elf = ELFFile(fh)
        pie = elf.header["e_type"] == "ET_DYN"
        textrel = False
        dyn = elf.get_section_by_name(".dynamic")
        for tag in (dyn.iter_tags() if dyn else []):
            if tag.entry.d_tag == "DT_TEXTREL" or (tag.entry.d_tag == "DT_FLAGS" and tag.entry.d_val & 4):
                textrel = True
    return [("a position-independent executable (ELF type DYN)", pie,
             "" if pie else "the file is a fixed-address executable"),
            ("no text relocations", not textrel,
             "" if not textrel else "the loader would have to patch read-only memory "
             "(see the linker's warning)")]
