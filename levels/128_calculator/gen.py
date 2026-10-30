"""Reference evaluator for level 128 (it also defines the language)."""

M = (1 << 64) - 1


class Error(Exception):
    pass


def wrap(v):
    v &= M
    return v - (1 << 64) if v >> 63 else v


def evaluate(text):
    s = text.split("\n")[0]
    pos = 0

    def peek():
        nonlocal pos
        while pos < len(s) and s[pos] == " ":
            pos += 1
        return s[pos] if pos < len(s) else ""

    def expr():
        nonlocal pos
        v = term()
        while peek() in ("+", "-"):
            op = s[pos]
            pos += 1
            r = term()
            v = wrap(v + r if op == "+" else v - r)
        return v

    def term():
        nonlocal pos
        v = factor()
        while peek() in ("*", "/"):
            op = s[pos]
            pos += 1
            r = factor()
            if op == "*":
                v = wrap(v * r)
            else:
                if r == 0 or (v == -(1 << 63) and r == -1):
                    raise Error
                q = abs(v) // abs(r)
                v = q if (v < 0) == (r < 0) else -q
        return v

    def factor():
        nonlocal pos
        c = peek()
        if c == "-":
            pos += 1
            return wrap(-factor())
        if c == "(":
            pos += 1
            v = expr()
            if peek() != ")":
                raise Error
            pos += 1
            return v
        if c.isdigit():
            start = pos
            while pos < len(s) and s[pos].isdigit():
                pos += 1
            v = int(s[start:pos])
            if v > (1 << 63) - 1:
                raise Error
            return v
        raise Error

    try:
        v = expr()
        if peek() != "":
            raise Error
        return f"{v}\n", 0
    except Error:
        return "error\n", 1


def case(name, text):
    out, code = evaluate(text)
    return {"name": name, "stdin": text + "\n", "expect": {"stdout": out, "exit": code}}


def rand_expr(rng, depth=0):
    r = rng.random()
    if depth > 4 or r < 0.3:
        return str(rng.choice([rng.randrange(10), rng.randrange(1000), rng.getrandbits(40)]))
    if r < 0.4:
        return "-" + rand_expr(rng, depth + 1)
    if r < 0.55:
        return "(" + rand_expr(rng, depth + 1) + ")"
    op = rng.choice("+-*/")
    sp = rng.choice(["", " "])
    return rand_expr(rng, depth + 1) + sp + op + sp + rand_expr(rng, depth + 1)


def fixed_tests(ctx):
    return [case("1 + 2 * 3", "1 + 2 * 3"), case("(1 + 2) * 3", "(1 + 2) * 3"),
            case("-7 / 2", "-7 / 2"), case("1 +", "1 +")]


BAD = ["", "(2", "2)", "2 3", "4 / 0", "a", "1 ++ 2", "()", "9223372036854775808",
       "--5", "-(-9223372036854775807 - 1) / -1"]


def generate(rng, count, ctx):
    out = [case(f"edge {b!r}", b) for b in BAD]
    out += [case("big", "9223372036854775807 + 1"), case("spaces", "  12 *( 3 -  5 )  ")]
    out += [case(f"random {i}", rand_expr(rng)[:200]) for i in range(count)]
    return out
