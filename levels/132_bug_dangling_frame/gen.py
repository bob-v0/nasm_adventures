M = (1 << 64) - 1


def case(name, a, b, c, d):
    text = f"{a},{b}\n{c},{d}\n"
    return {"name": name, "regs": {"rdi": a, "rsi": b, "rdx": c, "rcx": d},
            "expect": {"regs": {"rax": len(text)},
                       "mem": [{"sym": "report", "str": text + "\u0000"}]}}


def fixed_tests(ctx):
    return [case("(1, 2) and (30, 40)", 1, 2, 30, 40)]


def generate(rng, count, ctx):
    pick = lambda: rng.choice([0, M, rng.randrange(1000), rng.getrandbits(64)])
    return [case(f"random {i}", pick(), pick(), pick(), pick()) for i in range(count)]
