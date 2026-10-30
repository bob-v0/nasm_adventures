import string

MS = 1_000_000


def check(test, m):
    """Every line write at least 400 ms after the previous one, and not much more."""
    writes = [t for t, fd, n in m.kernel.writes if fd == 1][1:]   # skip "slept ..."
    problems = []
    for a, b in zip(writes, writes[1:]):
        gap = b - a
        if gap < 400 * MS:
            problems.append(f"two lines only {gap / MS:.3f} ms apart (the minimum is 400 ms)")
            break
        if gap > 405 * MS:
            problems.append(f"a {gap / MS:.3f} ms gap: sleep only as long as needed")
            break
    return problems


def case(name, lines):
    text = "".join(ln + "\n" for ln in lines)
    return {"name": name, "stdin": text,
            "expect": {"stdout": "slept 1250 ms\n" + text, "exit": 0, "check": True}}


def fixed_tests(ctx):
    return [case("three lines", ["tick", "tock", "tick"]), case("no input", [])]


def generate(rng, count, ctx):
    return [case(f"random {i}", ["".join(rng.choice(string.ascii_lowercase) for _ in range(rng.randrange(1, 30)))
                                 for _ in range(rng.randrange(1, 12))]) for i in range(count)]
