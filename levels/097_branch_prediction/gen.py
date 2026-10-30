def case(name, data, hidden=False, budget=None):
    n = len(data)
    t = {"name": name, "hidden": hidden, "regs": {"rdi": "@values", "rsi": n},
         "mem": [{"sym": "values", "hex": bytes(data).hex()}] if data else [],
         "expect": {"regs": {"rax": sum(b for b in data if b >= 128)}, "per": [max(n, 1), "byte"]}}
    if budget:
        t["expect"]["max_cycles"] = int(budget * n) + 1000   # (+ cold cache misses at the start)
    return t


def fixed_tests(ctx):
    import random
    r = random.Random(97)
    data = [r.randrange(256) for _ in range(2000)]
    return [case("2000 sorted bytes", sorted(data)),
            case("2000 random bytes", data, budget=3.0)]


def generate(rng, count, ctx):
    out = [case("nothing", [], True), case("all small", [5] * 300, True),
           case("all big", [200] * 2000, True, budget=3.0)]
    for i in range(count):
        n = rng.choice([1500, 2000, 2500])
        out.append(case(f"{n} random bytes", [rng.randrange(256) for _ in range(n)], True, budget=3.0))
    return out
