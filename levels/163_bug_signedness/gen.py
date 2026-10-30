M = (1 << 64) - 1


def s(v):
    return v - (1 << 64) if v >> 63 else v


def case(name, a, b, d):
    sa, sb = s(a), s(b)
    q = abs(sa) // abs(sb) * (1 if (sa < 0) == (sb < 0) else -1)
    dd = d - 256 if d >= 128 else d
    return {"name": name, "regs": {"rdi": a, "rsi": b}, "mem": [{"sym": "delta", "u8": d}],
            "expect": {"regs": {"rax": max(sa, sb) & M, "rbx": q & M, "rcx": (sa + dd) & M}}}


def fixed_tests(ctx):
    return [case("a=100, b=7, delta=3", 100, 7, 3),
            case("a=-100, b=7, delta=-3", (-100) & M, 7, 253)]


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        a = rng.choice([rng.getrandbits(64), rng.randrange(-500, 500) & M])
        b = rng.choice([rng.randrange(1, 100), (-rng.randrange(1, 100)) & M, rng.getrandbits(64) | 1])
        if a == 1 << 63 and s(b) == -1:
            b = 5
        out.append(case(f"random {i}", a, b, rng.randrange(256)))
    return out
