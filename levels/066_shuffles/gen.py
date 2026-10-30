GUARD = 48


def case(name, data, rng, hidden=False, budget=True):
    n = len(data)
    guard = rng.randbytes(GUARD)
    t = {"name": name, "hidden": hidden, "regs": {"rdi": "@buffer", "rsi": n},
         "mem": [{"sym": "buffer", "hex": (data + guard).hex()}],
         "expect": {"mem": [{"sym": "buffer", "hex": (data[::-1] + guard).hex()}],
                    "per": [max(n, 1), "byte"]}}
    if budget:
        t["expect"]["max_cycles"] = int(0.3 * n) + 800
    return t


def fixed_tests(ctx):
    import random
    rng = random.Random(66)
    return [case("'hello, world'", b"hello, world", rng, budget=False),
            case("the alphabet", bytes(range(65, 91)), rng, budget=False),
            case("100 bytes", rng.randbytes(100), rng, budget=False),
            case("8 KiB", rng.randbytes(8192), rng)]


def generate(rng, count, ctx):
    out = [case("nothing", b"", rng, True, False), case("one byte", b"x", rng, True, False)]
    for n in (15, 16, 17, 31, 32, 33, 47, 48, 63, 64, 65):
        out.append(case(f"{n} bytes", rng.randbytes(n), rng, True, False))
    for i in range(count):
        n = rng.randrange(5000, 39000)
        out.append(case(f"{n} bytes", rng.randbytes(n), rng, True))
    return out
