def case(name, n):
    fib, a, b = [], 0, 1
    for _ in range(n):
        fib.append(a)
        a, b = b, (a + b) & ((1 << 64) - 1)
    return {"name": name, "regs": {"rdi": n},
            "expect": {"regs": {"rax": n},
                       "mem": ([{"sym": "results", "u64": fib}] if fib else [])
                       + [{"sym": "ring_corrupted", "u64": 0}]}}


def fixed_tests(ctx):
    return [case("first 10 Fibonacci numbers", 10), case("n = 1", 1)]


def generate(rng, count, ctx):
    return [case("n = 93", 93), case("n = 0", 0)] + [case(f"n = {n}", n) for n in
                                                     rng.sample(range(2, 93), count)]
