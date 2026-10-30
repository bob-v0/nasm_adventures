STEPS = 18000          # the reference needs about 10 000-12 000


def case(name, inject, hidden=False, plain=False):
    return {"name": name, "hidden": hidden, "inject": {"tso": True, "quantum": 400, **inject},
            "expect": {"exit": 0, "mem": [{"sym": "total", "u64": 100}], "check": True,
                       "plain": plain}}


def check(test, m):
    problems = []
    if m.steps > STEPS:
        problems.append(f"{m.steps} instructions for 100 short critical sections (a sleeping lock "
                        f"needs under {STEPS}): waiting threads spin through their turns instead "
                        "of sleeping")
    lock = m.build.symbols["the_lock"]
    on_lock = [s for s in m.syscalls if str(s).startswith("futex(") and s.args and s.args[0] == lock]
    if test.expect["plain"] and len(on_lock) > 10:
        problems.append(f"{len(on_lock)} futex calls on the lock with almost no contention: lock and "
                        "unlock should make a syscall only when someone actually waits")
    return problems


def fixed_tests(ctx):
    return [case("one schedule", {"schedule": 0}, plain=True),
            case("many schedules", {"schedule_sweep": {"count": 15}})]


def generate(rng, count, ctx):
    return [case("more schedules", {"schedule_sweep": {"count": 15}, "quantum": 150}, hidden=True)]
