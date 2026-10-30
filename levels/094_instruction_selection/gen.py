def case(name, data, hidden=False, budget=None):
    n = len(data)
    t = {"name": name, "hidden": hidden, "regs": {"rdi": "@values", "rsi": n},
         "mem": [{"sym": "values", "hex": bytes(data).hex()}] if data else [],
         "expect": {"regs": {"rax": sum(b % 10 for b in data)}, "per": [max(n, 1), "byte"]}}
    if budget:
        t["expect"]["max_cycles"] = int(budget * n) + 1000
    return t


def fixed_tests(ctx):
    import random
    r = random.Random(94)
    return [case("0..255", list(range(256))),
            case("2000 random bytes", [r.randrange(256) for _ in range(2000)], budget=15)]


def generate(rng, count, ctx):
    return [case("nothing", [], True), case("255s", [255] * 100, True)] + [
        case(f"random {i}", [rng.randrange(256) for _ in range(1500)], True, budget=15)
        for i in range(count)]
