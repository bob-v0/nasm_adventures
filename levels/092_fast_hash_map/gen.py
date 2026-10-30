import struct

PUTS, GETS = 1500, 3000


def keyset(kind, rng, n):
    if kind == "random":
        return rng.sample(range(1, 1 << 63), n)
    if kind == "counters":
        start = rng.randrange(1, 1 << 20)
        return list(range(start, start + n))
    if kind == "addresses":            # 4 KiB-aligned, like pages or big allocations
        base = 0x7F0000000000
        return [base + 4096 * i for i in rng.sample(range(1, 1 << 24), n)]
    raise ValueError(kind)


def case(kind, rng, hidden=False, puts=PUTS, gets=GETS, budget=50):
    distinct = keyset(kind, rng, puts * 3 // 4)
    keys = distinct + [rng.choice(distinct) for _ in range(puts - len(distinct))]   # updates
    values = [rng.randrange(1, 1 << 63) for _ in keys]
    model = {}
    for k, v in zip(keys, values):
        model[k] = v
    absent = keyset(kind, rng, gets)
    absent = [k for k in absent if k not in model][:gets // 2]
    queries = [rng.choice(distinct) for _ in range(gets - len(absent))] + absent
    rng.shuffle(queries)
    want = [model.get(q, 0) for q in queries]
    pack = lambda xs: struct.pack(f"<{len(xs)}Q", *xs).hex()   # noqa: E731
    return {"name": f"{kind} keys: {puts} puts, {gets} gets", "hidden": hidden,
            "inject": {"warm_all": True},
            "mem": [{"sym": "nput", "u64": puts}, {"sym": "nget", "u64": len(queries)},
                    {"sym": "put_keys", "hex": pack(keys)}, {"sym": "put_values", "hex": pack(values)},
                    {"sym": "get_keys", "hex": pack(queries)}],
            "expect": {"exit": 0, "mem": [{"sym": "results", "hex": pack(want)}],
                       "max_cycles": budget * (puts + len(queries)) + 3000,
                       "per": [puts + len(queries), "operation"]}}


def fixed_tests(ctx):
    import random
    rng = random.Random(92)
    return [case("random", rng), case("counters", rng), case("addresses", rng)]


def generate(rng, count, ctx):
    return [case(kind, rng, hidden=True) for kind in ("random", "addresses")][:count + 1]
