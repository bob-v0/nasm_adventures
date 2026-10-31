def case(name, date, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"rtc": f"{date}T12:00:00"},
            "expect": {"serial": f"Hello, serial port! Today is {date}.\r\n"}}


def fixed_tests(ctx):
    return [case("1 January 2025", "2025-01-01")]


def generate(rng, count, ctx):
    return [case(f"another day ({i})", f"{rng.randrange(1999, 2099)}-{rng.randrange(1, 13):02d}-"
                 f"{rng.randrange(1, 29):02d}", True) for i in range(count)]


def audit(build):
    from ring.checks import disassemble
    ins = disassemble(build)
    ints = [ops for _, mn, ops in ins if mn == "int"]
    return [("talks to the hardware directly (no int)", not ints,
             f"found int {', '.join(ints)}" if ints else ""),
            ("uses in and out", any(mn == "in" for _, mn, _ in ins) and any(mn == "out" for _, mn, _ in ins), "")]
