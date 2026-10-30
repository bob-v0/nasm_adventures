M = (1 << 64) - 1


def s(v):
    return v - (1 << 64) if v >> 63 else v


def expect(a, b):
    sa, sb = s(a), s(b)
    return {"rax": abs(sa) & M, "rbx": min(sa, sb) & M, "rcx": max(a, b),
            "rdx": ((sa > 0) - (sa < 0)) & M, "r8": int(a == b)}


EDGE = [0, 1, M, 1 << 63, (1 << 63) - 1]


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        a = rng.choice(EDGE + [rng.getrandbits(64)] * 3)
        b = rng.choice(EDGE + [a, rng.getrandbits(64)] * 2)
        out.append({"name": f"random {i}", "regs": {"rdi": a, "rsi": b},
                    "expect": {"regs": expect(a, b)}})
    return out
