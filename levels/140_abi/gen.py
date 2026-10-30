M = (1 << 64) - 1


def case(name, x, a, b, c):
    return {"name": name, "regs": {"rdi": x, "rsi": a, "rdx": b, "rcx": c},
            "expect": {"regs": {"rax": (a * x * x + b * x + c) & M},
                       "mem": [{"sym": "ring_calls", "u64": 1}]}}


def fixed_tests(ctx):
    return [case("x=3: 2x^2 + 5x + 7", 3, 2, 5, 7)]


def generate(rng, count, ctx):
    return [case(f"random {i}", *(rng.choice([rng.getrandbits(64), rng.randrange(100)]) for _ in range(4)))
            for i in range(count)]
