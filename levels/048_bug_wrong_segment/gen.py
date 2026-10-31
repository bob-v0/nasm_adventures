MENU = ["Boot menu", "  1. Linux", "  2. FreeDOS"]


def case(name, bios, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"bios": bios},
            "expect": {"check": True}}


def check(test, run, regs, screen, serial):
    for y, row in enumerate(screen):
        if row == MENU[0]:
            if screen[y:y + 3] == MENU:
                return []
            return [f"the menu should be {MENU}, the screen shows {screen[y:y + 3]}"]
    return ["no 'Boot menu' line on the screen"]


def fixed_tests(ctx):
    return [case("SeaBIOS (QEMU's BIOS)", "seabios"), case("another BIOS", "odd")]


def witness_test(w, ctx):
    from ring.qemu import PROFILES
    if set(w) != {"bios"} or w["bios"] not in PROFILES:
        raise ValueError('the witness is a BIOS: `;! witness bios = "odd"` (or "seabios")')
    return case("witness", w["bios"])
