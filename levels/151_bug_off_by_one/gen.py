M = (1 << 64) - 1


def case(name, rng, n, m):
    src, dst = rng.randbytes(32), rng.randbytes(33)
    nums = [rng.getrandbits(64) for _ in range(16)]
    buf, fill = rng.randbytes(16), rng.randbytes(16)
    return {"name": name, "regs": {"rdx": n, "rsi": m},
            "mem": [{"sym": "src", "hex": src.hex()}, {"sym": "dst", "hex": dst.hex()},
                    {"sym": "nums", "u64": nums}, {"sym": "buf", "hex": buf.hex()},
                    {"sym": "fill", "hex": fill.hex()}],
            "expect": {"regs": {"rax": sum(nums[:m]) & M},
                       "flags": {"DF": 0},
                       "mem": [{"sym": "dst", "hex": (src[:n] + dst[n:]).hex()},
                               {"sym": "buf", "hex": (buf[:1] + buf[:15]).hex()},
                               {"sym": "fill", "hex": "ff" * 16}]}}


def fixed_tests(ctx):
    import random
    rng = random.Random(151)
    return [case("n = 5, m = 3", rng, 5, 3)]


def generate(rng, count, ctx):
    return [case(f"random {i}", rng, rng.choice([0, 32, rng.randrange(33)]),
                 rng.choice([1, 16, rng.randrange(1, 17)])) for i in range(count)]
