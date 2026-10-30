THREADS, ROUNDS = 4, 15
SLACK = 2       # "I want it" is logged a few instructions before the lock really queues


def case(name, inject, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"tso": True, "quantum": 120, **inject},
            "expect": {"exit": 0, "check": True}}


def check(test, m):
    import struct
    syms = m.build.symbols
    n = struct.unpack("<Q", m.read(syms["nevents"], 8))[0]
    events = struct.unpack(f"<{n}I", m.read(syms["events"], 4 * n))
    wanting, worst = {}, (0, None)
    got = 0
    for e in events:
        kind, t = e >> 8, e & 0xFF
        if kind == 1:
            wanting[t] = 0
        elif kind == 2:
            wanting.pop(t, None)
            for other in wanting:
                wanting[other] += 1
                if wanting[other] > worst[0]:
                    worst = (wanting[other], other)
            got += 1
    problems = []
    if got != THREADS * ROUNDS:
        problems.append(f"{got} critical sections logged, expected {THREADS * ROUNDS}")
    if worst[0] > THREADS - 1 + SLACK:
        problems.append(f"thread {worst[1]} waited while others got the lock {worst[0]} times "
                        f"(a fair lock: at most {THREADS - 1}, plus {SLACK} for the moment "
                        "between logging and asking)")
    return problems


def fixed_tests(ctx):
    return [case("one schedule", {"schedule": 0}),
            case("many schedules", {"schedule_sweep": {"count": 20}})]


def generate(rng, count, ctx):
    return [case("more schedules", {"schedule_sweep": {"count": 20}, "quantum": 60}, hidden=True)]


def witness_test(w, ctx):
    if set(w) != {"schedule"} or not isinstance(w["schedule"], int) or w["schedule"] < 0:
        raise ValueError("the witness is a schedule number: `;! witness schedule = 7`")
    return case("witness", {"schedule": w["schedule"]})
