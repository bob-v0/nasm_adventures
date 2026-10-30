M = (1 << 64) - 1


def case(name, n):
    s = f"{n}\n"
    return {"name": name, "regs": {"rdi": n}, "expect": {"regs": {"rax": len(s)}, "stdout": s}}


def fixed_tests(ctx):
    return [case("42", 42), case("0", 0)]


def generate(rng, count, ctx):
    return [case("2^64 - 1", M)] + [case(f"random {i}", rng.choice([rng.getrandbits(64),
                                                                    rng.randrange(1000)]))
                                    for i in range(count)]
