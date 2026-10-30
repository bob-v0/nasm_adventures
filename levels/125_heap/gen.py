def workload(rng, nops, max_size):
    ops, live, peak, cur, total = [], {}, 0, 0, 0
    for _ in range(nops):
        free_slots = [s for s in range(64) if s not in live]
        if live and (not free_slots or rng.random() < 0.45):
            s = rng.choice(sorted(live))
            ops += [2, s, 0]
            cur -= live.pop(s)
        else:
            s = rng.choice(free_slots)
            size = rng.choice([rng.randrange(1, 64), rng.randrange(1, max_size)])
            ops += [1, s, size]
            live[s] = size
            cur += size
            total += size
            peak = max(peak, cur)
    return ops, peak, total


def case(name, rng, nops, max_size):
    ops, peak, total = workload(rng, nops, max_size)
    limit = 3 * peak + 64 * 1024
    return {"name": f"{name} (peak {peak} bytes live, {total} allocated)",
            "mem": [{"sym": "ops", "u64": ops}, {"sym": "nops", "u64": len(ops) // 3}],
            "expect": {"regs": {"rax": 0}, "mem": [{"sym": "ring_error", "u64": 0}],
                       "heap_max": limit}}


def fixed_tests(ctx):
    import random
    rng = random.Random(125)
    return [case("small workload", rng, 40, 200)]


def generate(rng, count, ctx):
    out = []
    while len(out) < count:
        t = case(f"random {len(out)}", rng, rng.choice([400, 600]), rng.choice([100, 2000, 6000]))
        total = int(t["name"].split(", ")[1].split()[0])
        if total > 1.5 * t["expect"]["heap_max"]:   # only workloads that need reuse
            out.append(t)
    return out
