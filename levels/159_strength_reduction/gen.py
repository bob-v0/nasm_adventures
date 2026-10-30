M = (1 << 64) - 1


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        x = rng.choice([rng.getrandbits(64), rng.randrange(100), M - rng.randrange(20), rng.getrandbits(32)])
        out.append({"name": f"random {i}", "regs": {"rdi": x},
                    "expect": {"regs": {"rax": x // 10, "rbx": x % 10, "rcx": (x * 45) & M,
                                        "r8": x >> 3, "r9": (x << 10) & M}}})
    return out
