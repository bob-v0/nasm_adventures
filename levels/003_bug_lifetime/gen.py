"""Level 3: a list readers walk without a lock while the first CPU replaces its nodes.
The CPUs run truly in parallel (QEMU's multi-threaded mode)."""

UPDATES = 400


def case(name, cpus, hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"qemu_args": ["-smp", str(cpus)], "parallel": True},
            "expect": {"serial": f"updates: {UPDATES}, freed nodes seen: 0\r\n", "timeout": 40}}


def fixed_tests(ctx):
    return [case("four CPUs", 4), case("four CPUs, again", 4)]


def generate(rng, count, ctx):
    return [case("three CPUs", 3, True), case("four CPUs, a third time", 4, True)]
