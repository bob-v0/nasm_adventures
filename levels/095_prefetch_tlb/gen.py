import struct

POOL = 4 << 20


def case(name, lengths, rng, hidden=False, budget=None):
    slots = rng.sample(range(POOL // 64), sum(lengths))
    mem, heads, total, k = [], [], 0, 0
    for n in lengths:
        mine, slots = slots[:n], slots[n:]
        for i, s in enumerate(mine):
            value = rng.randrange(1, 1000)
            total += value
            nxt = {"ptr": f"pool+{mine[i + 1] * 64}"} if i + 1 < n else {"ptr": 0}
            mem.append({"sym": "pool", "offset": s * 64, **nxt})
            mem.append({"sym": "pool", "offset": s * 64 + 8, "u64": value})
        heads.append(f"pool+{mine[0] * 64}" if n else 0)
    for i, h in enumerate(heads):
        mem.append({"sym": "heads", "offset": 8 * i, "ptr": h})
    nodes = sum(lengths)
    t = {"name": name, "hidden": hidden, "regs": {"rdi": "@heads", "rsi": len(lengths)},
         "mem": mem, "expect": {"regs": {"rax": total}, "per": [max(nodes, 1), "node"]}}
    if budget:
        t["expect"]["max_cycles"] = int(budget * nodes) + 3000
    return t


def fixed_tests(ctx):
    import random
    rng = random.Random(95)
    return [case("one short list", [5], rng), case("8 lists of 200 nodes", [200] * 8, rng, budget=45)]


def generate(rng, count, ctx):
    return [case("empty lists too", [0, 3, 0, 7], rng, True),
            case("uneven lists", [400, 50, 300, 10, 250, 200, 1, 180], rng, True, budget=45)]
