GUARD = 48


def case(name, data, amount, rng, hidden=False, budget=True):
    n = len(data)
    guard = rng.randbytes(GUARD)
    want = bytes(min(255, b + amount) for b in data) + guard
    t = {"name": name, "hidden": hidden, "regs": {"rdi": "@pixels", "rsi": n, "rdx": amount},
         "mem": [{"sym": "pixels", "hex": (bytes(data) + guard).hex()}],
         "expect": {"mem": [{"sym": "pixels", "hex": want.hex()}], "per": [max(n, 1), "pixel"]}}
    if budget:
        t["expect"]["max_cycles"] = int(0.4 * n) + 800
    return t


def fixed_tests(ctx):
    import random
    rng = random.Random(67)
    return [case("16 pixels", [rng.randrange(256) for _ in range(16)], 40, rng, budget=False),
            case("21 pixels", [rng.randrange(256) for _ in range(21)], 100, rng, budget=False),
            case("a 64x64 photo", [rng.randrange(256) for _ in range(4096)], 30, rng)]


def generate(rng, count, ctx):
    out = [case("nothing", [], 50, rng, True, False), case("5 pixels", [250, 1, 128, 255, 0], 9, rng, True, False),
           case("all white", [255] * 1000, 200, rng, True),
           case("amount 0", [rng.randrange(256) for _ in range(333)], 0, rng, True)]
    for i in range(count):
        n = rng.randrange(2000, 20000)
        out.append(case(f"photo {i}", [rng.randrange(256) for _ in range(n)], rng.randrange(1, 256),
                        rng, True))
    return out
