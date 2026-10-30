import struct

NUMBERS = 16384
GUARD = 16


def case(name, xs, threshold, rng, hidden=False, budget=True):
    n = len(xs)
    kept = [x for x in xs if x > threshold]
    guard = rng.randbytes(4 * GUARD)
    start = 4 * (NUMBERS - n)
    t = {"name": name, "hidden": hidden,
         "regs": {"rdi": f"@numbers+{start}", "rsi": n, "rdx": threshold & 0xFFFFFFFF, "rcx": "@kept"},
         "mem": [{"sym": "numbers", "offset": start, "hex": struct.pack(f"<{n}i", *xs).hex()},
                 {"sym": "kept", "hex": (bytes(4 * len(kept)) + guard).hex()}],
         "inject": {"cpu": "avx512", "unmap": [{"sym": "guard", "size": 4096}],
                    "warm": [{"sym": "numbers", "offset": start, "size": 4 * n},
                             {"sym": "kept", "size": 4 * n + 64}]},
         "expect": {"regs": {"rax": len(kept)},
                    "mem": [{"sym": "kept", "hex": (struct.pack(f"<{len(kept)}i", *kept) + guard).hex()}],
                    "per": [max(n, 1), "element"]}}
    if budget:
        t["expect"]["max_cycles"] = int(0.4 * n) + 500
    return t


def rand(rng, n, lo=-1000, hi=1000):
    return [rng.randint(lo, hi) for _ in range(n)]


def fixed_tests(ctx):
    import random
    rng = random.Random(59)
    return [case("1..20, over 10", list(range(1, 21)), 10, rng, budget=False),
            case("negative numbers", [-5, 3, -1, -9, 0, 7, -2], -3, rng, budget=False),
            case("5000 random", rand(rng, 5000), 0, rng)]


def generate(rng, count, ctx):
    out = [case("nothing", [], 0, rng, True, False), case("none pass", rand(rng, 37), 5000, rng, True, False),
           case("all pass", rand(rng, 50), -5000, rng, True, False),
           case("extremes", [-2 ** 31, 2 ** 31 - 1, 0, -1, 1], -1, rng, True, False)]
    for i in range(count):
        n = rng.randrange(3000, NUMBERS)
        out.append(case(f"{n} random", rand(rng, n, -10 ** 9, 10 ** 9), rng.randint(-10 ** 9, 10 ** 9), rng, True))
    return out
