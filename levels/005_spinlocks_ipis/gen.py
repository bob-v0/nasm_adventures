"""Level 5: every CPU works through shared jobs (a spinlock), then the window page is
remapped round after round (a TLB shootdown). The CPUs run truly in parallel here (QEMU's
multi-threaded mode, not one at a time): an unlocked race really races."""

JOBS, ROUNDS = 4000, 8


def total():
    return sum(((i * 2654435761) & 0xFFFFFFFF) >> 16 & 0xFFFF for i in range(JOBS)) & 0xFFFFFFFF


def want():
    out = f"jobs done: {JOBS}, total {total()}\r\n"
    return out + "".join(f"round {k}: every cpu sees {k}\r\n" for k in range(1, ROUNDS + 1))


def case(name, cpus, hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"qemu_args": ["-smp", str(cpus)], "parallel": True},
            "expect": {"serial": want(), "timeout": 15}}


def fixed_tests(ctx):
    return [case("two CPUs", 2), case("four CPUs", 4)]


def generate(rng, count, ctx):
    return [case("eight CPUs", 8, True), case("three CPUs", 3, True), case("four CPUs again", 4, True),
            case("six CPUs", 6, True)]
