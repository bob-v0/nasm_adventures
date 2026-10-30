def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        a, b, c, d = (rng.getrandbits(64) for _ in range(4))
        tests.append({"name": f"random {i}", "regs": {"rax": a, "rbx": b, "rcx": c, "rdx": d},
                      "expect": {"regs": {"rax": b, "rbx": c, "rcx": d, "rdx": a}}})
    return tests
