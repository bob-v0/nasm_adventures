def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        data = bytes(rng.randrange(0x21, 0x7F) for _ in range(8))
        tests.append({"name": f"random {i}", "stdin": data.decode(),
                      "expect": {"stdout": f"echo: {data[::-1].decode()}\n", "exit": 8}})
    return tests
