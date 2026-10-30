M = (1 << 64) - 1
MAX, MIN = (1 << 63) - 1, -(1 << 63)


def wrap(v):
    v &= M
    return v - (1 << 64) if v >> 63 else v


def case(name, a, b, text, ch):
    n = len(a)
    stdin = f"{n}\n{' '.join(map(str, a))}\n{' '.join(map(str, b))}\n{text}\n{ord(ch)}\n"
    out = (f"dot = {wrap(sum(x * y for x, y in zip(a, b)))}\n"
           f"sorted ={''.join(' ' + str(v) for v in sorted(a, reverse=True))}\n"
           f"count = {text.count(ch)}\n")
    return {"name": name, "stdin": stdin, "expect": {"stdout": out, "exit": 0}}


def fixed_tests(ctx):
    return [case("small", [3, -1, 2], [4, 5, 6], "banana bread", "a")]


def generate(rng, count, ctx):
    out = [case("extremes (watch the comparator)", [MAX, MIN, 0, -1, 1, MIN, MAX], [1] * 7,
                "no match here", "z"),
           case("empty arrays", [], [], "x", "x")]
    for i in range(count):
        n = rng.randrange(0, 40)
        a = [rng.choice([rng.randrange(-1000, 1000), rng.randrange(MIN, MAX)]) for _ in range(n)]
        b = [rng.randrange(-1000, 1000) for _ in range(n)]
        text = "".join(rng.choice("abc xyz") for _ in range(rng.randrange(1, 100))).strip() or "a"
        out.append(case(f"random {i}", a, b, text, rng.choice("abcxyz ")))
    return out
