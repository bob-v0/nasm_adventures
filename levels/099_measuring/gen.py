# What a careful measurement on the game's CPU model gives (warm, fenced, minimum,
# minus the overhead of measuring an empty function).
TRUTH = {"f_chain": 174, "f_sum": 62, "f_div": 323, "f_branchy": 55}
WHAT = {"f_chain": "60 dependent multiplies", "f_sum": "512 bytes added up",
        "f_div": "8 divisions", "f_branchy": "a 40-step loop"}


def case(fn, noise, hidden=False):
    return {"name": f"{fn}: {WHAT[fn]} (interrupts: pattern {noise})", "hidden": hidden,
            "regs": {"rdi": f"@{fn}"}, "inject": {"noise": noise},
            "expect": {"check": True, "fn": fn}}


def check(test, m):
    fn = test.expect["fn"]
    got, want = m.reg("rax"), TRUTH[fn]
    if abs(got - want) <= max(8, want // 10):
        return []
    return [f"you measured {got} cycles for {fn}; a careful measurement gives about {want} "
            "(within 10%)"]


def fixed_tests(ctx):
    return [case(fn, 1) for fn in TRUTH]


def generate(rng, count, ctx):
    return [case(fn, rng.randrange(2, 10_000), hidden=True) for fn in TRUTH for _ in range(count)]
