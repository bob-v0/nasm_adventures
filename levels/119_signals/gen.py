def case(name, at=None):
    sigs = [{"at": at, "sig": 2}] if at else []
    out = ("caught SIGINT\n" if at else "no SIGINT\n") + "recovered from SIGSEGV\n"
    return {"name": name, "inject": {"signals": sigs}, "expect": {"stdout": out, "exit": 0}}


def fixed_tests(ctx):
    return [case("Ctrl+C after 500 instructions", 500), case("no Ctrl+C")]


def generate(rng, count, ctx):
    return [case(f"Ctrl+C after {k} instructions", k) for k in
            sorted(rng.sample(range(300, 200000), count))]
