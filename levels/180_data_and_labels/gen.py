def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        v = rng.getrandbits(64)
        ch = rng.randrange(0x21, 0x7F)
        tests.append({
            "name": f"random {i}",
            "mem": [{"sym": "input", "u64": v}, {"sym": "greeting", "offset": 7, "u8": ch}],
            "expect": {"regs": {"rax": "@greeting", "rbx": ch},
                       "mem": [{"sym": "slot", "u64": v}, {"sym": "counter", "u16": 0xBEEF}]},
        })
    return tests
