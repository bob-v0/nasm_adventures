DATE = "06/23/99"                # SeaBIOS's, at F000:FFF5


def case(name, seg, off, text, hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"note": {"seg": seg, "off": off, "text": text}},
            "expect": {"check": True, "note": text}}


def check(test, run, regs, screen, serial):
    want = ["Hello, segments!", test.expect["note"], f"BIOS date: {DATE}"]
    for y, row in enumerate(screen):
        if row == want[0]:
            got = screen[y:y + 3]
            for k, (w, g) in enumerate(zip(want, got + [""] * 3)):
                if w != g:
                    return [f"line {k + 1} after 'Hello, segments!': expected {w!r}, got {g!r}"]
            return []
    return ["no line on the screen says exactly 'Hello, segments!'"]


def fixed_tests(ctx):
    return [case("a note at 1234:5678", 0x1234, 0x5678, "The quick brown segment jumps over the lazy offset.")]


def generate(rng, count, ctx):
    words = ["far", "near", "segment", "offset", "paragraph", "real", "mode", "pointer", "byte",
             "sixteen", "times", "plus"]
    out = []
    for i in range(count):
        seg = rng.randrange(0x0800, 0x8000)          # (physical 0x8000-0x8FEFF: free)
        off = rng.randrange(0, 0xFF00)
        text = " ".join(rng.choice(words) for _ in range(rng.randrange(3, 8))).capitalize() + "."
        out.append(case(f"a note at {seg:04X}:{off:04X}", seg, off, text, True))
    return out
