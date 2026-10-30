import struct

THREADS, NODES = 4, 30
N = THREADS * NODES


def case(name, inject, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"tso": True, "quantum": 40, **inject},
            "expect": {"exit": 0, "check": True}}


def check(test, m):
    syms = m.build.symbols
    n = struct.unpack("<Q", m.read(syms["npopped"], 8))[0]
    got = sorted(struct.unpack(f"<{min(n, 2 * N)}Q", m.read(syms["popped"], 8 * min(n, 2 * N))))
    want = list(range(1, N + 1))
    if got == want:
        return []
    lost = sorted(set(want) - set(got))
    twice = sorted({v for v in got if got.count(v) > 1})
    return ["the nodes that came out are wrong: " + "; ".join(x for x in (
        f"{len(lost)} never came out (e.g. {lost[:3]})" if lost else "",
        f"{len(twice)} came out twice (e.g. {twice[:3]})" if twice else "") if x)]


def fixed_tests(ctx):
    return [case("one schedule", {"schedule": 0}),
            case("many schedules", {"schedule_sweep": {"count": 25}})]


def generate(rng, count, ctx):
    return [case("more schedules", {"schedule_sweep": {"count": 25}, "quantum": 20}, hidden=True)]
