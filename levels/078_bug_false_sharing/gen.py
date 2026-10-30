def case(name, quantum, hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"tso": True, "quantum": quantum, "schedule": 0},
            "expect": {"stdout": "events 1200\n", "exit": 0, "max_cycles": 4000}}


def fixed_tests(ctx):
    return [case("4 threads, 300 events each", 3)]


def generate(rng, count, ctx):
    return [case("4 threads, other timing", 4, hidden=True)]
