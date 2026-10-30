def case(name, inject, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"tso": True, "quantum": 40, **inject},
            "expect": {"stdout": "double owners: 0\n", "exit": 0}}


def fixed_tests(ctx):
    return [case("one schedule", {"schedule": 0}),
            case("many schedules", {"schedule_sweep": {"count": 40}})]


def generate(rng, count, ctx):
    return [case("more schedules", {"schedule_sweep": {"count": 40}, "quantum": 20}, hidden=True)]


def witness_test(w, ctx):
    if set(w) != {"schedule"} or not isinstance(w["schedule"], int) or w["schedule"] < 0:
        raise ValueError("the witness is a schedule number: `;! witness schedule = 7`")
    return case("witness", {"schedule": w["schedule"]})
