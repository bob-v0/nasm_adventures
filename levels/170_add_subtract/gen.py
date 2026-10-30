M = (1 << 64) - 1


def expect(a, b, c):
    return {"rax": (a + b - c) & M, "rbx": -a & M, "rcx": (c + 1) & M, "r8": (b - 1) & M,
            "r9": (c - 2 * a) & M}


def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        a, b, c = (rng.choice([rng.getrandbits(64), rng.randrange(-5, 5) & M]) for _ in range(3))
        tests.append({"name": f"random {i}", "regs": {"rdi": a, "rsi": b, "rdx": c},
                      "expect": {"regs": expect(a, b, c)}})
    return tests
