M = (1 << 64) - 1


def sx(v, bits):
    v &= (1 << bits) - 1
    return (v - (1 << bits) if v >> (bits - 1) else v) & M


def expect(a):
    return {"rbx": a & 0xFF, "rcx": sx(a, 16), "rdx": sx(a, 32), "rsi": (a >> 8) & 0xFF,
            "rdi": a & 0xFFFFFFFF, "r8": (a & ~0xFF & M) | 0x7F}


def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        a = rng.getrandbits(64)
        if i % 3 == 0:
            a |= 0x80008080  # force sign bits in each width
        tests.append({"name": f"random {i}", "regs": {"rax": a},
                      "expect": {"regs": expect(a)}})
    return tests
