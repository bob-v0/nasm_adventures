"""Level 4: one page, two frames taking turns; readers on every other CPU check each
snapshot of the page is one round's. The CPUs run truly in parallel (QEMU's
multi-threaded mode): the race is real, so it shows up most runs, not every one."""

ROUNDS = 300


def case(name, cpus, hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"qemu_args": ["-smp", str(cpus)], "parallel": True},
            "expect": {"serial": f"rounds: {ROUNDS}, torn reads: 0\r\n", "timeout": 30}}


def fixed_tests(ctx):
    return [case("four CPUs", 4), case("eight CPUs", 8)]


def generate(rng, count, ctx):
    return [case("four CPUs again", 4, True), case("six CPUs", 6, True), case("eight CPUs again", 8, True)]
