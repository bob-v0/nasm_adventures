def case(name, inject, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"tso": True, "quantum": 60, **inject},
            "expect": {"exit": 0, "stderr": "", "check": True}}


def check(test, m):
    import struct
    syms = m.build.symbols
    twice, unordered = struct.unpack("<II", m.read(syms["problems"], 8))
    processed = struct.unpack("<I", m.read(syms["processed"], 4))[0]
    out = []
    if processed != 60:
        out.append(f"{processed} of 60 messages processed")
    if twice:
        out.append(f"an actor ran on two workers at once ({twice} times)")
    if unordered:
        out.append(f"{unordered} messages arrived before an earlier one from the same sender")
    leaked = [b for b in m.kernel.blocks.values() if not b["freed"]]
    if leaked:
        out.append(f"{len(leaked)} messages never freed")
    return out


def fixed_tests(ctx):
    return [case("one schedule", {"schedule": 0}),
            case("many schedules", {"schedule_sweep": {"count": 25}})]


def generate(rng, count, ctx):
    return [case("more schedules", {"schedule_sweep": {"count": 25}, "quantum": 20}, hidden=True)]
