def case(name, p, c, n, cap, hidden=False, schedules=12):
    return {"name": name, "hidden": hidden, "argv": ["./queue", str(p), str(c), str(n), str(cap)],
            "inject": {"tso": True, "quantum": 120, "schedule_sweep": {"count": schedules}},
            "expect": {"exit": 0, "stderr": "", "check": True}}


def check(test, m):
    import struct
    _, p, c, n, cap = test.argv
    p, c, n, cap = int(p), int(c), int(n), int(cap)
    syms = m.build.symbols
    count = struct.unpack("<Q", m.read(syms["ring_log_len"], 8))[0]
    raw = m.read(syms["ring_log"], 16 * count)
    log = [struct.unpack_from("<QQ", raw, 16 * i) for i in range(count)]
    sent = [v for k, v in log if k == 1]
    got = [v for k, v in log if k == 2]
    problems = []
    want = sorted(q * 1000 + i for q in range(p) for i in range(n))
    if sorted(got) != want:
        lost = sorted(set(want) - set(got))
        dup = sorted({v for v in got if got.count(v) > 1})
        bogus = sorted(set(got) - set(want))
        problems.append("received values are wrong: " + "; ".join(x for x in (
            f"lost {lost[:5]}" if lost else "", f"received twice {dup[:5]}" if dup else "",
            f"never sent {bogus[:5]}" if bogus else "") if x))
    for q in range(p):
        mine = [v for v in got if v // 1000 == q]
        if mine != sorted(mine):
            problems.append(f"producer {q}'s values came out of order: {mine[:8]}")
            break
    inside = 0
    for k, _ in log:
        inside += 1 if k == 1 else -1
        if inside > cap + c:
            problems.append(f"{inside} values were sent but not yet received: a channel of "
                            f"capacity {cap} must make senders wait")
            break
    if m.steps > 400 * p * n + 20000:
        problems.append(f"{m.steps} instructions for {p * n} values: are waiting threads spinning "
                        "instead of sleeping on a futex?")
    return problems


def fixed_tests(ctx):
    return [case("1 producer, 1 consumer, capacity 1", 1, 1, 6, 1),
            case("2 producers, 1 consumer, capacity 2", 2, 1, 5, 2),
            case("1 producer, 3 consumers, capacity 4", 1, 3, 10, 4)]


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        p, c = rng.randrange(1, 5), rng.randrange(1, 5)
        out.append(case(f"random {i}: {p} producers, {c} consumers", p, c, rng.randrange(1, 12),
                        rng.choice([1, 2, 3, 8]), hidden=True, schedules=6))
    return out
