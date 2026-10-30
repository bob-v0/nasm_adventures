import string


def case(name, data, pipe=False):
    t = {"name": name, "stdin_hex": data.hex(), "expect": {"stdout_hex": data.hex(), "exit": 0}}
    if pipe:
        t["inject"] = {"short_reads": True, "short_writes": True}
    return t


def fixed_tests(ctx):
    text = ("All work and no play makes Jack a dull boy.\n" * 40).encode()
    return [case("from a file", text), case("through a pipe", text, pipe=True)]


def generate(rng, count, ctx):
    out = [case("empty input through a pipe", b"", pipe=True)]
    for i in range(count):
        data = rng.randbytes(rng.choice([1, 100, 4096, 70000, rng.randrange(50000)]))
        out.append(case(f"random {i} ({len(data)} bytes)", data, pipe=True))
    return out
