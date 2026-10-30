def case(name, inject, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"tso": True, "quantum": 60, **inject},
            "expect": {"exit": 0, "stderr": "", "check": True}}


def check(test, m):
    leaked = [b for b in m.kernel.blocks.values() if not b["freed"]]
    return [f"{len(leaked)} heap block(s) never freed (an actor whose count never reached 0?)"] \
        if leaked else []


def fixed_tests(ctx):
    return [case("one schedule", {"schedule": 0}),
            case("many schedules", {"schedule_sweep": {"count": 30}})]


def generate(rng, count, ctx):
    return [case("more schedules", {"schedule_sweep": {"count": 30}, "quantum": 20}, hidden=True)]


def witness_test(w, ctx):
    if set(w) != {"schedule"} or not isinstance(w["schedule"], int) or w["schedule"] < 0:
        raise ValueError("the witness is a schedule number: `;! witness schedule = 7`")
    return case("witness", {"schedule": w["schedule"]})
