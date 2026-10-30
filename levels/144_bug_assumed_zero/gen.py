import string


def case(name, s):
    b = s.encode()
    return {"name": name, "mem": [{"sym": "text", "hex": (b + bytes(64 - len(b))).hex()}],
            "expect": {"regs": {"rax": sum(c in "aeiouAEIOU" for c in s),
                                "rbx": sum(int(c) for c in s if c.isdigit()), "rcx": len(s)}}}


def fixed_tests(ctx):
    return [case("Area 51, sector 7", "Area 51, sector 7")]


def generate(rng, count, ctx):
    out = [case("empty", "")]
    for i in range(count):
        s = "".join(rng.choice(string.ascii_letters + string.digits + " .,!") for _ in range(rng.randrange(0, 63)))
        out.append(case(f"random {i}", s))
    return out
