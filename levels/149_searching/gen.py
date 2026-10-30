import bisect

M = (1 << 64) - 1


def case(name, vals, n, key):
    return {"name": name, "regs": {"rdi": key, "rsi": n},
            "mem": [{"sym": "arr", "u64": vals + [M] * (1024 - len(vals))}],
            "expect": {"regs": {"rax": bisect.bisect_left(vals[:n], key)}}}


def fixed_tests(ctx):
    v = [2, 3, 3, 3, 8, 13]
    return [case("key 3 in 2 3 3 3 8 13", v, 6, 3), case("key 9", v, 6, 9),
            case("key above everything", v, 6, 100), case("empty array", [], 0, 5)]


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        n = rng.choice([0, 1, 2, 1024, 1023, rng.randrange(1025)])
        spread = rng.choice([4, 1000, 1 << 63, M])
        vals = sorted(rng.randrange(spread) for _ in range(n))
        key = rng.choice([0, M, rng.randrange(spread)] + ([rng.choice(vals)] if vals else []))
        out.append(case(f"random {i} (n={n})", vals, n, key))
    return out
