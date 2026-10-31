WANT = "received 1000 items in order, sum 500500\r\n"
PERIODS = [173, 211, 257, 300, 347, 401, 463, 512, 577, 641, 709, 787, 853, 911, 997, 1061,
           1129, 1201, 1301, 1409, 1511, 1601, 1709, 1823]


def case(name, period, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"cmdline": f"period={period}"},
            "expect": {"serial": WANT, "timeout": 20}}


def fixed_tests(ctx):
    return [case(f"period {p}", p) for p in PERIODS[:12]]


def generate(rng, count, ctx):
    return [case(f"period {p}", p, True) for p in PERIODS[12:]] + \
        [case(f"period {p}", p, True) for p in sorted(rng.sample(range(150, 2500), count))]


def witness_test(w, ctx):
    if set(w) != {"period"} or not isinstance(w["period"], int) or not 100 <= w["period"] <= 100000:
        raise ValueError("the witness is a timer period from 100 to 100000: `;! witness period = 300`")
    return case("witness", w["period"])
