import struct

THREADS, ROUNDS = 4, 24
N = THREADS * ROUNDS


def case(name, rng, hidden=False, sweep=15):
    values = [0] + [rng.getrandbits(48) | 1 for _ in range(N)]
    return {"name": name, "hidden": hidden,
            "mem": [{"sym": "values", "hex": struct.pack(f"<{N + 1}Q", *values).hex()}],
            "inject": {"tso": True, "quantum": 60, "schedule_sweep": {"count": sweep}},
            "expect": {"exit": 0, "check": True, "values": values[1:]}}


def check(test, m):
    syms = m.build.symbols
    q = lambda name, n: struct.unpack(f"<{n}Q", m.read(syms[name], 8 * n))   # noqa: E731
    problems = []
    tickets = q("tickets", N)
    if any(t != 1 for t in tickets):
        dup = [i for i, t in enumerate(tickets) if t > 1][:5]
        miss = [i for i, t in enumerate(tickets) if t == 0][:5]
        problems.append("atomic_fetch_add: tickets " + (f"{dup} were handed out twice" if dup else "")
                        + (" and " if dup and miss else "") + (f"{miss} never" if miss else ""))
    values = test.expect["values"]
    if q("biggest", 1)[0] != max(values):
        problems.append(f"atomic_max: ended at {q('biggest', 1)[0]}, but the biggest value was "
                        f"{max(values)}")
    came_back = sorted(list(q("swapped", N)) + [q("token", 1)[0]])
    if came_back != sorted([0] + values):
        lost = len(set(values) - set(came_back))
        problems.append(f"atomic_swap: {lost} value(s) went in and never came back out "
                        "(two swaps overlapped)")
    return problems


def fixed_tests(ctx):
    import random
    return [case("4 threads, 24 rounds each", random.Random(90))]


def generate(rng, count, ctx):
    return [case(f"another run {i + 1}", rng, hidden=True) for i in range(count)]
