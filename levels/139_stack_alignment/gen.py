M = (1 << 64) - 1


def case(name, n, k):
    return {"name": name, "regs": {"rdi": n, "rsi": k},
            "expect": {"regs": {"rax": sum((i * k) ** 2 for i in range(1, n + 1)) & M},
                       "mem": [{"sym": "ring_calls", "u64": n}, {"sym": "ring_misaligned", "u64": 0}]}}


def fixed_tests(ctx):
    return [case("n=3, k=1: 1 + 4 + 9", 3, 1), case("n=0", 0, 5)]


def generate(rng, count, ctx):
    return [case(f"random {i}", rng.randrange(0, 40), rng.choice([1, rng.getrandbits(32)]))
            for i in range(count)]
