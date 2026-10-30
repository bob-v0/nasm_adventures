M = (1 << 64) - 1
PIPES = [(lambda x: (x + 3) & M, lambda x: x & 1, lambda a, b: (a + b) & M),
         (lambda x: (x * x) & M, lambda x: x > 10, max)]


def case(name, vals, which, rng):
    f, p, r = PIPES[which]
    mapped = [f(v) for v in vals]
    kept = [v for v in mapped if p(v)]
    acc = 0
    for v in kept:
        acc = r(acc, v)
    tail = [rng.getrandbits(64) for _ in range(64 - len(vals))]
    return {"name": name, "regs": {"rdi": len(vals), "rsi": which},
            "mem": [{"sym": "data", "u64": vals + tail}],
            "expect": {"regs": {"rax": acc},
                       "mem": [{"sym": "data", "u64": kept} if kept else {"sym": "ring_count", "u64": 0},
                               {"sym": "ring_count", "u64": len(kept)},
                               {"sym": "ring_misaligned", "u64": 0}]}}


def fixed_tests(ctx):
    import random
    rng = random.Random(131)
    return [case("add 3, keep odd, sum: 1 2 3 4", [1, 2, 3, 4], 0, rng),
            case("square, keep > 10, max: 2 5 3 4", [2, 5, 3, 4], 1, rng)]


def generate(rng, count, ctx):
    out = [case("empty", [], 0, rng)]
    for i in range(count):
        n = rng.randrange(0, 65)
        vals = [rng.choice([rng.randrange(100), rng.getrandbits(64)]) for _ in range(n)]
        out.append(case(f"random {i}", vals, rng.randrange(2), rng))
    return out
