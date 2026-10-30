M = (1 << 64) - 1


def case(name, x):
    s = x - (1 << 64) if x >> 63 else x
    u, d, h = str(x), str(s), hex(x)
    return {"name": name, "regs": {"rdi": x},
            "mem": [{"sym": b, "str": "#" * 24} for b in ("dec_u", "dec_s", "hex")],
            "expect": {"regs": {"rax": len(u), "rbx": len(d), "rcx": len(h)},
                       "mem": [{"sym": "dec_u", "str": u + "#" * (24 - len(u))},
                               {"sym": "dec_s", "str": d + "#" * (24 - len(d))},
                               {"sym": "hex", "str": h + "#" * (24 - len(h))}]}}


def generate(rng, count, ctx):
    edge = [0, 1, 9, 10, 15, 16, 99, 100, M, 1 << 63, (1 << 63) - 1, (1 << 63) + 1]
    xs = edge + [rng.choice([rng.getrandbits(64), rng.getrandbits(rng.randrange(1, 64)),
                             (-rng.randrange(1, 10 ** 6)) & M]) for _ in range(count - len(edge))]
    return [case(f"random {i}", x) for i, x in enumerate(xs)]
