import string


def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        lines = ["".join(rng.choice(string.ascii_lowercase + " :") for _ in range(15)) + "\n"
                 for _ in range(3)]
        tests.append({"name": f"random {i}", "mem": [{"sym": "lines", "str": "".join(lines)}],
                      "expect": {"stdout": "".join(lines), "exit": 3}})
    return tests
