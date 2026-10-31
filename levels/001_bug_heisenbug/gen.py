"""Level 1: reference counts, shared by every CPU. Run one CPU at a time (QEMU's usual,
deterministic mode) it's always right; with the CPUs truly in parallel, it isn't."""

WANT = "objects: 64, freed at the end: 64, used after free: 0\r\n"


def case(name, cpus, parallel=True, hidden=False):
    inj = {"qemu_args": ["-smp", str(cpus)]}
    if parallel:
        inj["parallel"] = True
    return {"name": name, "hidden": hidden, "inject": inj, "expect": {"serial": WANT, "timeout": 60}}


def fixed_tests(ctx):
    return [case("four CPUs, one at a time", 4, parallel=False),
            case("two CPUs, in parallel", 2), case("four CPUs, in parallel", 4)]


def generate(rng, count, ctx):
    return [case("three CPUs, in parallel", 3, hidden=True), case("four CPUs, in parallel, again", 4, hidden=True)]
