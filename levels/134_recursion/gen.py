def hanoi(n, a, b, c, out):
    if n:
        hanoi(n - 1, a, c, b, out)
        out += bytes([a, b])
        hanoi(n - 1, c, b, a, out)


def case(name, n, a=1, b=3, c=2):
    out = bytearray()
    hanoi(n, a, b, c, out)
    return {"name": name, "regs": {"rdi": n, "rsi": a, "rdx": b, "rcx": c, "r8": "@moves"},
            "expect": {"regs": {"rax": f"@moves+{len(out)}"},
                       "mem": [{"sym": "moves", "hex": out.hex()}] if out else []}}


def fixed_tests(ctx):
    return [case("n = 2", 2), case("n = 0: nothing to move", 0)]


def generate(rng, count, ctx):
    out = [case("n = 12", 12)]
    for i in range(count):
        pegs = rng.sample([1, 2, 3], 3)
        out.append(case(f"random {i}", rng.randrange(1, 12), *pegs))
    return out
