M = (1 << 64) - 1


def words(v):
    return [(v >> (64 * i)) & M for i in range(4)]


def case(name, a, b, i, j, k):
    a2 = a | (1 << i)
    b2 = b & ~(1 << j)
    return {
        "name": name, "regs": {"rdi": i, "rsi": j, "rdx": k},
        "mem": [{"sym": "setA", "u64": words(a)}, {"sym": "setB", "u64": words(b)}],
        "expect": {"regs": {"rax": bin(a2).count("1"), "rbx": (a2 & -a2).bit_length() - 1,
                            "rcx": b2 >> k & 1, "r8": (b2.bit_length() - 1) & M},
                   "mem": [{"sym": "setA", "u64": words(a2)}, {"sym": "setB", "u64": words(b2)}]},
    }


def generate(rng, count, ctx):
    out = []
    for n in range(count):
        dens = rng.choice([0, 0.02, 0.5])
        a = sum(1 << i for i in range(256) if rng.random() < dens)
        b = sum(1 << i for i in range(256) if rng.random() < dens)
        i, j = rng.randrange(256), rng.randrange(256)
        k = rng.choice([j, rng.randrange(256)])
        out.append(case(f"random {n}", a, b, i, j, k))
    out.append(case("B becomes empty", 0, 1 << 200, 5, 200, 200))
    return out
