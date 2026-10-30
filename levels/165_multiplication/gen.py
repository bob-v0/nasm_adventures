M = (1 << 64) - 1


def s(v):
    return v - (1 << 64) if v >> 63 else v


def expect(a, b):
    p = a * b
    sp = s(a) * s(b)
    return {"rax": p & M, "rdx": p >> 64, "r8": int(not -(1 << 63) <= sp < (1 << 63)),
            "r9": (a * 37) & M, "r10": sp & M}


def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        a = rng.choice([rng.getrandbits(64), rng.getrandbits(32), (-rng.getrandbits(31)) & M])
        b = rng.choice([rng.getrandbits(64), rng.getrandbits(31), (-rng.getrandbits(31)) & M])
        tests.append({"name": f"random {i}", "regs": {"rdi": a, "rsi": b},
                      "expect": {"regs": expect(a, b)}})
    return tests
