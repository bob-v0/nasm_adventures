def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        v = rng.getrandbits(64)
        tests.append({"name": f"random {i}", "mem": [{"sym": "secret", "u64": v}],
                      "expect": {"exit": v & 0xFF, "syscalls": ["exit"]}})
    return tests
