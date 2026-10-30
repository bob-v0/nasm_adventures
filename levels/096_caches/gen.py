import struct


def case(name, n, rng, hidden=False, budget=None):
    vals = [rng.getrandbits(64) for _ in range(n * n)]
    t = {"name": name, "hidden": hidden, "regs": {"rdi": "@dst_matrix", "rsi": "@src_matrix", "rdx": n},
         "mem": [{"sym": "src_matrix", "hex": struct.pack(f"<{n * n}Q", *vals).hex()}] if n else [],
         "inject": {"warm": [{"sym": "src_matrix", "size": 8 * n * n},
                             {"sym": "dst_matrix", "size": 8 * n * n}]},
         "expect": {"per": [max(n * n, 1), "element"]}}
    want = [vals[i * n + j] for j in range(n) for i in range(n)]
    if n:
        t["expect"]["mem"] = [{"sym": "dst_matrix", "hex": struct.pack(f"<{n * n}Q", *want).hex()}]
    if budget:
        t["expect"]["max_cycles"] = int(budget * n * n) + 2000
    return t


def fixed_tests(ctx):
    import random
    rng = random.Random(96)
    return [case("3 x 3", 3, rng), case("128 x 128", 128, rng, budget=2.5)]


def generate(rng, count, ctx):
    return [case("1 x 1", 1, rng, True), case("17 x 17", 17, rng, True),
            case("64 x 64", 64, rng, True, budget=2.5)]
