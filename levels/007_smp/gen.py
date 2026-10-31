"""Level 7: every CPU says hello. The order depends on timing; the lines must be whole
(a lock), one per CPU, and the count right."""

MACHINES = {
    "two CPUs": (["-smp", "2"], [0, 1]),
    "four CPUs": (["-smp", "4"], [0, 1, 2, 3]),
    "eight CPUs": (["-smp", "8"], list(range(8))),
    "two sockets of three cores": (["-smp", "6,sockets=2,cores=3"], [0, 1, 2, 4, 5, 6]),
    "three CPUs": (["-smp", "3"], [0, 1, 2]),
}


def case(name, hidden=False):
    args, ids = MACHINES[name]
    return {"name": name, "hidden": hidden, "inject": {"qemu_args": args},
            "expect": {"check": True, "ids": ids, "timeout": 20}}


def check(test, run, regs, screen, serial):
    ids = test.expect["ids"]
    lines = serial.decode("latin-1").split("\r\n")
    if lines and lines[-1] == "":
        lines.pop()
    want_last = f"{len(ids)} cpus said hello"
    if not lines or lines[-1] != want_last:
        return [f"the last line should be `{want_last}`; the output: {lines}"]
    hellos = sorted(lines[:-1])
    want = sorted(f"hello from apic id {i}" for i in ids)
    if hellos != want:
        bad = [l for l in lines[:-1] if l not in want]
        return [f"expected one `hello from apic id N` from each CPU (ids {ids}), whole lines, "
                f"in any order; got {lines[:-1]}" + (f" (not one of them: {bad[:2]}: CPUs "
                "printing at the same time?)" if bad else "")]
    return []


def fixed_tests(ctx):
    return [case("two CPUs"), case("four CPUs")]


def generate(rng, count, ctx):
    return [case(n, True) for n in list(MACHINES)[2:]]
