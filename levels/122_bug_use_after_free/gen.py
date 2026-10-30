WORDS = "ring stack heap free list node page byte word bit kernel signal pipe fork".split()


def case(name, words):
    seen, out = set(), []
    for w in words:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return {"name": name, "stdin": "".join(w + "\n" for w in words),
            "expect": {"stdout": "".join(w + "\n" for w in out), "exit": 0}}


def fixed_tests(ctx):
    return [case("a b a c b", ["a", "b", "a", "c", "b"]), case("no repeats", ["ring", "zero"])]


def generate(rng, count, ctx):
    out = [case("empty input", []), case("all the same", ["x"] * 6)]
    for i in range(count):
        out.append(case(f"random {i}", [rng.choice(WORDS) for _ in range(rng.randrange(1, 60))]))
    return out
