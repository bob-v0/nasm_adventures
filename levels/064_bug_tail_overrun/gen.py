STRINGS = 65536


def text(rng, n):
    return bytes(rng.randrange(1, 256) for _ in range(n))


def case(name, s, offset=None, hidden=False, budget=True):
    """offset: where the string starts in `strings`; None = right at the end of it."""
    n = len(s)
    if offset is None:
        offset = STRINGS - (n + 1)
    t = {"name": name, "hidden": hidden, "regs": {"rdi": f"@strings+{offset}"},
         "mem": [{"sym": "strings", "offset": offset, "hex": (s + b"\0").hex()}],
         "inject": {"unmap": [{"sym": "guard", "size": 4096}]},
         "expect": {"regs": {"rax": n}, "per": [max(n, 1), "byte"]}}
    if budget:
        t["expect"]["max_cycles"] = int(0.35 * n) + 800
    return t


def fixed_tests(ctx):
    import random
    rng = random.Random(64)
    return [case("'hello, world'", b"hello, world", 1000, budget=False),
            case("an empty string", b"", 3000, budget=False),
            case("10 KB of text", text(rng, 10000), 7),
            case("a name at the end of a page", b"Ada Lovelace", budget=False)]


def generate(rng, count, ctx):
    out = [case("empty, at the end", b"", None, True, False),
           case("15 at the end", text(rng, 15), None, True, False),
           case("aligned start", text(rng, 40), 4096, True, False)]
    for i in range(count):
        n = rng.choice([rng.randrange(1, 40), rng.randrange(40, 3000), rng.randrange(3000, 30000)])
        at_end = i % 2 == 0
        off = None if at_end else rng.randrange(0, STRINGS - n - 4096)
        out.append(case(f"{n} bytes" + (" at the end of a page" if at_end else ""), text(rng, n),
                        off, True, n >= 3000))
    return out


def witness_test(w, ctx):
    import random
    if set(w) != {"n"} or not isinstance(w["n"], int) or not 0 <= w["n"] < 60000:
        raise ValueError("the witness is a string length from 0 to 59999: `;! witness n = 4` "
                         "(the game puts it right before an unmapped page)")
    return case("witness", text(random.Random(w["n"]), w["n"]), None, budget=False)
