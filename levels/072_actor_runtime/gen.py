TOTAL = 2 * 3 * 7


def case(name, inject, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"tso": True, "quantum": 60, **inject},
            "expect": {"exit": 0, "stderr": "", "check": True}}


def check(test, m):
    import struct
    syms = m.build.symbols
    twice, _, unknown = struct.unpack("<III", m.read(syms["problems"], 12))
    processed = struct.unpack("<I", m.read(syms["processed"], 4))[0]
    out = []
    if processed != TOTAL:
        out.append(f"{processed} of {TOTAL} messages handled")
    if twice:
        out.append(f"an actor ran on two workers at once ({twice} times)")
    if unknown:
        out.append("behavior was called with something that isn't an actor")
    leaked = [b for b in m.kernel.blocks.values() if not b["freed"]]
    if leaked:
        out.append(f"{len(leaked)} heap block(s) never freed (allocated at "
                   f"{', '.join(sorted({b['alloc'] for b in leaked}))})")
    alive = [t.tid for t in m.threads[1:] if t.state != "exited"]
    if alive:
        out.append(f"threads {alive} still running at the end: rt_shutdown must stop them")
    return out


def fixed_tests(ctx):
    return [case("one schedule", {"schedule": 0}),
            case("many schedules", {"schedule_sweep": {"count": 25}})]


def generate(rng, count, ctx):
    return [case("more schedules", {"schedule_sweep": {"count": 25}, "quantum": 20}, hidden=True)]
