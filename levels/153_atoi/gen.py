import string

M = (1 << 64) - 1
GOOD = {10: string.digits, 16: string.hexdigits}


def parse(s):
    """The rules: optional + or -, then decimal digits or 0x/0X + hex digits, nothing else."""
    t, neg = s, False
    if t[:1] in ("+", "-"):
        neg, t = t[0] == "-", t[1:]
    base = 10
    if t[:2] in ("0x", "0X"):
        base, t = 16, t[2:]
    if not t or any(c not in GOOD[base] for c in t):
        return 0, 1
    v = int(t, base)
    if v > (1 << 63 if neg else (1 << 63) - 1):
        return 0, 2
    return (-v if neg else v) & M, 0


def case(name, s):
    v, status = parse(s)
    return {"name": name, "mem": [{"sym": "text", "str": s + "\0" * (48 - len(s))}],
            "expect": {"regs": {"rax": v, "rbx": status}}}


EDGE = ["0", "-0", "+7", "42", "-42", "0x1F", "0XfF", "-0x80", "9223372036854775807",
        "9223372036854775808", "-9223372036854775808", "-9223372036854775809",
        "0x7fffffffffffffff", "0x8000000000000000", "-0x8000000000000000",
        "18446744073709551616", "99999999999999999999999", "", "-", "+", "0x", "-0x",
        "12a", "1 2", " 12", "0xg", "+-3", "007", "0x0001"]


def generate(rng, count, ctx):
    out = [case(f"edge {s!r}", s) for s in EDGE]
    for i in range(count):
        kind = rng.choice(["dec", "hex", "bad"])
        sign = rng.choice(["", "", "-", "+"])
        if kind == "dec":
            s = sign + str(rng.getrandbits(rng.randrange(1, 66)))
        elif kind == "hex":
            s = sign + rng.choice(["0x", "0X"]) + format(rng.getrandbits(rng.randrange(1, 66)), rng.choice("xX"))
        else:
            s = sign + str(rng.randrange(1000)) + rng.choice("g.x-/:@ ") + str(rng.randrange(10))
        out.append(case(f"random {i}", s[:47]))
    return out


def fixed_tests(ctx):
    return [case("-123", "-123"), case("0x7f", "0x7f"), case("12x (invalid)", "12x"),
            case("2^63 (overflow)", "9223372036854775808")]
