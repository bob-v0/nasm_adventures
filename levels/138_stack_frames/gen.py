def case(name, depth, maxn):
    chain = ["ring_nest.after_bt"] + ["ring_nest.after_rec"] * (depth - 1) + ["ring_run.after_nest"]
    kept = chain[:maxn]
    mem = [{"sym": "frames", "offset": 8 * i, "ptr": sym} for i, sym in enumerate(kept)]
    return {"name": name, "regs": {"rdi": depth, "rsi": "@frames", "rdx": maxn},
            "expect": {"regs": {"rax": len(kept)}, "mem": mem}}


def fixed_tests(ctx):
    return [case("depth 3", 3, 16), case("depth 1", 1, 16)]


def generate(rng, count, ctx):
    return [case(f"random {i}", rng.randrange(1, 12), rng.choice([16, rng.randrange(1, 16)]))
            for i in range(count)]
