M = (1 << 64) - 1


def s(v):
    return v - (1 << 64) if v >> 63 else v


def case(name, vals, rng):
    n = len(vals)
    tail = [rng.getrandbits(64) for _ in range(200 - n)]
    srt = sorted(vals, key=s)
    return {"name": name, "regs": {"rsi": n},
            "mem": [{"sym": "arr", "u64": vals + tail}],
            "expect": {"mem": [{"sym": "arr", "u64": srt + tail}]}}


def fixed_tests(ctx):
    import random
    rng = random.Random(148)
    return [case("5 3 -1 4 1", [5, 3, (-1) & M, 4, 1], rng), case("empty", [], rng)]


def generate(rng, count, ctx):
    out = [case("200 in reverse (worst case)", [(200 - i) for i in range(200)], rng),
           case("already sorted", list(range(150)), rng),
           case("one element", [42], rng),
           case("extremes", [M, 1 << 63, (1 << 63) - 1, 0, 1], rng)]
    for i in range(count):
        n = rng.randrange(0, 201)
        kind = rng.choice(["random", "small", "dups"])
        vals = [rng.getrandbits(64) if kind == "random" else
                rng.randrange(-50, 50) & M if kind == "small" else rng.choice([7, (-7) & M, 0])
                for _ in range(n)]
        out.append(case(f"random {i} (n={n}, {kind})", vals, rng))
    return out
