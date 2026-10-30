M = (1 << 64) - 1
INT_MIN, INT_MAX = -(1 << 63), (1 << 63) - 1


def s(v):
    return v - (1 << 64) if v >> 63 else v


def expect(a, b):
    return {"rax": int(a + b > M), "rbx": int(not INT_MIN <= s(a) + s(b) <= INT_MAX),
            "rcx": int(a < b), "rdx": int(not INT_MIN <= s(a) - s(b) <= INT_MAX),
            "r8": int(s(a) < s(b)), "r9": int(a < b)}


EDGE = [0, 1, M, 1 << 63, (1 << 63) - 1, (1 << 63) + 1, 2]


def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        a = rng.choice(EDGE + [rng.getrandbits(64)] * 4)
        b = rng.choice(EDGE + [rng.getrandbits(64)] * 4)
        tests.append({"name": f"random {i}", "regs": {"rdi": a, "rsi": b},
                      "expect": {"regs": expect(a, b)}})
    return tests
