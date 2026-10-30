def case(name, p, c, n, cap, inject, hidden=False):
    return {"name": name, "hidden": hidden, "argv": ["./queue", str(p), str(c), str(n), str(cap)],
            "inject": {"tso": True, "quantum": 60, **inject},
            "expect": {"exit": 0, "stderr": "", "check": True}}


def check(test, m):
    import struct
    _, p, c, n, cap = test.argv
    p, n = int(p), int(n)
    count = struct.unpack("<Q", m.read(m.build.symbols["ring_log_len"], 8))[0]
    raw = m.read(m.build.symbols["ring_log"], 16 * count)
    got = sorted(struct.unpack_from("<Q", raw, 16 * i + 8)[0] for i in range(count)
                 if struct.unpack_from("<Q", raw, 16 * i)[0] & 0xFF == 2)
    want = sorted(q * 1000 + i for q in range(p) for i in range(n))
    return [] if got == want else [f"received {len(got)} of {len(want)} values"]


def fixed_tests(ctx):
    return [case("2 producers, 2 consumers, capacity 1", 2, 2, 8, 1, {"schedule": 0}),
            case("many schedules", 2, 2, 8, 1, {"schedule_sweep": {"count": 60}})]


def generate(rng, count, ctx):
    return [case("more schedules", 3, 2, 6, 2, {"schedule_sweep": {"count": 40}}, hidden=True)]


def witness_test(w, ctx):
    if set(w) != {"schedule"} or not isinstance(w["schedule"], int) or w["schedule"] < 0:
        raise ValueError("the witness is a schedule number: `;! witness schedule = 7`")
    return case("witness", 2, 2, 8, 1, {"schedule": w["schedule"]})
