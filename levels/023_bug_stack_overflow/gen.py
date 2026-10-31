"""Level 23: a recursive sum overflows the kernel stack into the data below it. Fixed, an
overflow must end in a clean #DF report (a guard page, and level 24's IST)."""

SAFE = [1, 5, 9, 12, 14]                # these fit in the stack
DEEP = [17, 20, 24, 27, 31, 33]         # these don't


def want(n):
    if n in SAFE:
        return {"serial": f"sum of squares 1..{n} = {sum(i * i for i in range(1, n + 1))}\r\n"}
    return {"check": True, "n": n}


def case(name, n, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"cmdline": f"n={n}"},
            "expect": {**want(n), "timeout": 10}}


def check(test, run, regs, screen, serial):
    import re
    n = test.expect["n"]
    if re.fullmatch(rb"sum of squares 1\.\.%d = #DF at 0x[0-9a-f]{16}, error code 0x0{16}\r\n" % n,
                    serial):
        return []
    return [f"n = {n} doesn't fit in the kernel stack: expected `sum of squares 1..{n} = ` and "
            f"then the #DF handler's report (`#DF at 0x..., error code 0x0000000000000000`); "
            f"got {serial[:120]!r}"]


def fixed_tests(ctx):
    return [case("n = 9", 9), case("n = 14", 14)]


def generate(rng, count, ctx):
    return [case(f"n = {n}", n, True) for n in (1, 5, 12)] + \
        [case(f"n = {n}", n, True) for n in DEEP]


def witness_test(w, ctx):
    if set(w) != {"n"} or not isinstance(w["n"], int) or not 16 <= w["n"] <= 35:
        raise ValueError("the witness is an n from 16 to 35 that the original gets wrong: "
                         "`;! witness n = 20`")
    return case("witness", w["n"])
