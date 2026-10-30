import string

PAIRS = {")": "(", "]": "[", "}": "{"}


def balanced(s):
    st = []
    for c in s:
        if c in "([{":
            st.append(c)
        elif c in PAIRS:
            if not st or st.pop() != PAIRS[c]:
                return 0
    return int(not st)


def case(name, s, rng):
    b = s.encode()
    out = rng.randbytes(64)
    return {"name": name, "mem": [{"sym": "text", "hex": (b + bytes(64 - len(b))).hex()},
                                  {"sym": "out", "hex": out.hex()}],
            "expect": {"regs": {"rax": balanced(s)},
                       "mem": [{"sym": "out", "hex": (b[::-1] + b"\0").hex()}]}}


def fixed_tests(ctx):
    import random
    rng = random.Random(142)
    return [case("f(a[i]) {}", "f(a[i]) {}", rng), case("([)]", "([)]", rng), case("empty", "", rng)]


def generate(rng, count, ctx):
    out = [case("(((", "(((", rng), case(")(", ")(", rng)]
    for i in range(count):
        n = rng.randrange(0, 63)
        if rng.random() < 0.5:   # build a balanced string, maybe break it
            s, st = "", []
            while len(s) < n:
                if st and rng.random() < 0.45:
                    s += {"(": ")", "[": "]", "{": "}"}[st.pop()]
                elif rng.random() < 0.5:
                    c = rng.choice("([{")
                    st.append(c)
                    s += c
                else:
                    s += rng.choice(string.ascii_letters + " +")
            s += "".join({"(": ")", "[": "]", "{": "}"}[c] for c in reversed(st))
            s = s[:62]
            if rng.random() < 0.3 and s:
                k = rng.randrange(len(s))
                s = s[:k] + rng.choice("()[]{}") + s[k + 1:]
        else:
            s = "".join(rng.choice("()[]{}ab ") for _ in range(n))
        out.append(case(f"random {i}", s, rng))
    return out
