M = (1 << 64) - 1


def fnv1a(data):
    h = 0xCBF29CE484222325
    for b in data:
        h = ((h ^ b) * 0x100000001B3) & M
    return h


def crc32c(data):
    c = 0xFFFFFFFF
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ (0x82F63B78 if c & 1 else 0)
    return c ^ 0xFFFFFFFF


def case(name, data):
    return {"name": name, "mem": [{"sym": "text", "hex": (data + bytes(128 - len(data))).hex()}],
            "expect": {"regs": {"rax": fnv1a(data), "rbx": crc32c(data)}}}


def fixed_tests(ctx):
    return [case('"hello"', b"hello"), case("empty string", b"")]


def generate(rng, count, ctx):
    return [case(f"random {i}", bytes(rng.randrange(1, 256) for _ in range(rng.randrange(0, 128))))
            for i in range(count)]
