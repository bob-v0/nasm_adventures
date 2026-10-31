WANT = "50 requests completed\r\n"


def case(name, delay, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"cmdline": f"delay={delay}"},
            "expect": {"serial": WANT, "timeout": 6}}


DELAYS = [2048, 487, 4096, 1000, 200, 333, 1512, 3001]


def fixed_tests(ctx):
    return [case(f"delay {d}", d) for d in DELAYS[:4]]


def generate(rng, count, ctx):
    return [case(f"delay {d}", d, True) for d in DELAYS[4:]] + \
        [case(f"delay {d}", d, True) for d in sorted(rng.sample(range(150, 5000), count))]


def witness_test(w, ctx):
    if set(w) != {"delay"} or not isinstance(w["delay"], int) or not 100 <= w["delay"] <= 100000:
        raise ValueError("the witness is a delay from 100 to 100000: `;! witness delay = 500`")
    return case("witness", w["delay"])
