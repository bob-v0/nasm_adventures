M = (1 << 64) - 1


def expect(x, y):
    return {"rax": x & -x & M, "rbx": x & (x - 1) & M, "rcx": int(x != 0 and x & (x - 1) == 0),
            "rdx": 1 << (x - 1).bit_length(), "r8": bin(x).count("1") & 1,
            "r9": abs(x - y)}


def case(name, x, y):
    return {"name": name, "regs": {"rdi": x, "rsi": y}, "expect": {"regs": expect(x, y)}}


def fixed_tests(ctx):
    return [case("x = 12, y = 20", 12, 20), case("x = 64 (a power of two), y = 1", 64, 1)]


def generate(rng, count, ctx):
    out = [case("x = 1", 1, 0), case("x = 2^63", 1 << 63, M), case("x = 2^63 - 1", (1 << 63) - 1, 0)]
    for i in range(count):
        x = rng.choice([rng.getrandbits(63) + 1, 1 << rng.randrange(64), rng.randrange(1, 100),
                        (1 << rng.randrange(1, 63)) + 1])
        out.append(case(f"random {i}", x, rng.choice([rng.getrandbits(64), x, 0])))
    return out
