M = (1 << 64) - 1


def expect(v):
    return {"rax": v & ~0xFFF & M, "rbx": v | 0xFFF, "rcx": v ^ (1 << 63), "rdx": ~v & M,
            "r8": (v + 0xFFF) & ~0xFFF & M, "r9": 0, "r10": int(v & 7 == 0)}


def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        v = rng.getrandbits(62)
        if i % 3 == 0:
            v &= ~7
        tests.append({"name": f"random {i}", "regs": {"rdi": v, "r9": rng.getrandbits(64)},
                      "expect": {"regs": expect(v)}})
    return tests
