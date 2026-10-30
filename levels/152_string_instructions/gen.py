def case(name, rng, n, fillbyte, s1, s2, df=False):
    src = rng.randbytes(64)
    dst = rng.randbytes(64)
    fill = rng.randbytes(32)
    b1 = (s1 + b"\0" * 64)[:64]
    b2 = (s2 + b"\0" * 64)[:64]
    cmp = (b1[:n] > b2[:n]) - (b1[:n] < b2[:n])
    regs = {"rdx": n, "r8": fillbyte}
    if df:
        regs["rflags"] = 0x602   # DF set by "earlier code"
    return {"name": name, "regs": regs,
            "mem": [{"sym": "src", "hex": src.hex()}, {"sym": "dst", "hex": dst.hex()},
                    {"sym": "fill", "hex": fill.hex()}, {"sym": "str1", "hex": b1.hex()},
                    {"sym": "str2", "hex": b2.hex()}],
            "expect": {"regs": {"rax": b1.index(0), "rbx": cmp & ((1 << 64) - 1)},
                       "mem": [{"sym": "dst", "hex": (src[:n] + dst[n:]).hex()},
                               {"sym": "fill", "hex": bytes([fillbyte & 0xFF]) .hex() * 32}]}}


def fixed_tests(ctx):
    import random
    rng = random.Random(152)
    return [case("copy 10, strings differ at byte 3", rng, 10, 0x41, b"hello", b"help!"),
            case("same, but DF was left set by earlier code", rng, 10, 0x41, b"hello", b"help!", df=True)]


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        n = rng.choice([0, 1, 64, rng.randrange(65)])
        a = bytes(rng.randrange(1, 256) for _ in range(rng.randrange(0, 63)))
        b = bytearray(a + bytes(rng.randrange(1, 256) for _ in range(5)))[:63]
        if b and rng.random() < 0.6:
            k = rng.randrange(len(b))
            b[k] = rng.randrange(1, 256)
        out.append(case(f"random {i}", rng, n, rng.getrandbits(64), a, bytes(b), df=rng.random() < 0.3))
    return out
