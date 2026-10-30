M = (1 << 64) - 1


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        n = rng.choice([0, 1, 64, rng.randrange(65)])
        vals = [rng.choice([rng.getrandbits(64), rng.randrange(100)]) for _ in range(64)]
        t = rng.choice([0, M, rng.getrandbits(64), rng.randrange(100)])
        used = vals[:n]
        out.append({"name": f"random {i} (n={n})", "regs": {"rsi": n, "rdx": t},
                    "mem": [{"sym": "arr", "u64": vals}],
                    "expect": {"regs": {"rax": sum(used) & M, "rbx": max(used, default=0),
                                        "rcx": sum(1 for v in used if v > t)}}})
    return out
