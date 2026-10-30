M = (1 << 64) - 1


def limbs(v, n):
    return [(v >> (64 * k)) & M for k in range(n)]


def case(name, a, n, b, m, rng):
    p = a * b
    garbage = [rng.getrandbits(64) for _ in range(16)]
    return {
        "name": name, "regs": {"rsi": n, "rcx": m},
        "mem": [{"sym": "numA", "u64": limbs(a, n) + [rng.getrandbits(64) for _ in range(8 - n)]},
                {"sym": "numB", "u64": limbs(b, m) + [rng.getrandbits(64) for _ in range(8 - m)]},
                {"sym": "product", "u64": garbage}],
        "expect": {"mem": [{"sym": "product", "u64": limbs(p, n + m) + garbage[n + m:]}]},
    }


def fixed_tests(ctx):
    import random
    rng = random.Random(1)
    return [case("1 limb x 1 limb: (2^64-1)^2", M, 1, M, 1, rng),
            case("2 limbs x 1 limb", (1 << 127) + 12345, 2, 1 << 63 | 7, 1, rng)]


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        n, m = rng.randrange(1, 9), rng.randrange(1, 9)
        kind = rng.choice(["random", "max", "sparse"])
        if kind == "max":
            a, b = (1 << 64 * n) - 1, (1 << 64 * m) - 1
        elif kind == "sparse":
            a, b = 1 << rng.randrange(64 * n), (1 << rng.randrange(64 * m)) | 1
        else:
            a, b = rng.getrandbits(64 * n), rng.getrandbits(64 * m)
        out.append(case(f"random {i} ({n}x{m} limbs, {kind})", a, n, b, m, rng))
    return out
