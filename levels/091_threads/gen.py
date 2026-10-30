import struct


def case(name, values, k, hidden=False, sweep=10):
    n = len(values)
    t = {"name": name, "hidden": hidden, "regs": {"rdi": "@values", "rsi": n, "rdx": k},
         "mem": [{"sym": "values", "hex": struct.pack(f"<{n}Q", *values).hex()}] if n else [],
         "inject": {"schedule_sweep": {"count": sweep}, "quantum": 300},
         "expect": {"regs": {"rax": sum(values) % (1 << 64)}, "check": True, "k": k}}
    return t


def check(test, m):
    k = test.expect["k"]
    clones = sum(str(s).startswith("clone(") for s in m.syscalls)
    if clones < k - 1:
        return [f"{k} threads were asked for, but clone was called {clones} times"]
    alive = [t.tid for t in m.threads[1:] if t.state != "exited"]
    if alive:
        return [f"threads {alive} were still running when the function returned: join them all"]
    return []


def fixed_tests(ctx):
    return [case("4 threads, 100 values", list(range(1, 101)), 4),
            case("1 thread", [5, 6, 7], 1)]


def generate(rng, count, ctx):
    out = [case("8 threads, fewer values than threads", [9, 9, 9], 8, True),
           case("3 threads, no values", [], 3, True)]
    for i in range(count):
        n, k = rng.randrange(50, 600), rng.randrange(2, 9)
        out.append(case(f"{k} threads, {n} values", [rng.getrandbits(40) for _ in range(n)], k, True))
    return out
