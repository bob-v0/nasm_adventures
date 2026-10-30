M = (1 << 64) - 1
LIMIT = 1 << 20


def expect(count, size):
    total = count * size + 16
    return total if total <= LIMIT else M


def case(name, count, size):
    return {"name": name, "regs": {"rdi": count, "rsi": size},
            "expect": {"regs": {"rax": expect(count, size)}}}


def fixed_tests(ctx):
    return [case("1000 records of 64 bytes", 1000, 64),
            case("100000 records of 64 bytes: too big", 100000, 64)]


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        c = rng.choice([rng.randrange(1, 5000), rng.getrandbits(64), 1 << rng.randrange(40, 64)])
        s = rng.choice([rng.randrange(1, 300), rng.getrandbits(64), 1 << rng.randrange(0, 30)])
        out.append(case(f"random {i}", c, s))
    out.append(case("product wraps to 0", 1 << 61, 8))
    out.append(case("header wraps", M - 7, 1))
    return out


def witness_test(w, ctx):
    unknown = set(w) - {"rdi", "rsi"}
    if unknown or "rdi" not in w or "rsi" not in w:
        raise ValueError("the witness needs exactly rdi (count) and rsi (size), "
                         "e.g. `;! witness rdi = 123, rsi = 456`")
    c, s = w["rdi"] & M, w["rsi"] & M
    return case("witness", c, s)
