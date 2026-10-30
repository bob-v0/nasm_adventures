M = (1 << 64) - 1


def case(name, data, rng):
    framed = bytes([len(data)]) + data
    return {"name": name, "regs": {"rdi": "@packet", "rsi": len(data)},
            "mem": [{"sym": "packet", "hex": (data + rng.randbytes(64 - len(data))).hex()}],
            "expect": {"regs": {"rax": sum(b * 31 + 7 for b in framed) & M},
                       "mem": [{"sym": "packet", "hex": framed.hex()},
                               {"sym": "ring_misaligned", "u64": 0},
                               {"sym": "ring_corrupted", "u64": 0}]}}


def fixed_tests(ctx):
    import random
    rng = random.Random(137)
    return [case('"hi!"', b"hi!", rng)]


def generate(rng, count, ctx):
    return [case(f"random {i}", rng.randbytes(rng.randrange(1, 60)), rng) for i in range(count)]
