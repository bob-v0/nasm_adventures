import string


def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        name = "".join(rng.choice(string.ascii_letters) for _ in range(8))
        tests.append({"name": f"random {i}", "mem": [{"sym": "name", "str": name}],
                      "expect": {"stdout": f"Hello, {name}!\n",
                                 "stderr": "warning: the walls have ears\n", "exit": 29}})
    return tests
