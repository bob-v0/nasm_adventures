import re
import struct

START = [1000, 1000, 1000, 1000]


def case(name, transfers, hidden=False, inject=None):
    table = b"".join(struct.pack("<qqq", *t) for t in transfers)
    return {"name": name, "hidden": hidden,
            "mem": [{"sym": "ntransfers", "u64": len(transfers)},
                    {"sym": "transfers", "hex": table.hex()}],
            "inject": inject or {"schedule_sweep": {"count": 60}},
            "expect": {"exit": 0, "check": True, "transfers": [list(t) for t in transfers]}}


def check(test, m):
    out = bytes(m.stdout).decode("latin-1")
    transfers = test.expect["transfers"]
    ok = {int(k): v == "ok" for k, v in re.findall(r"transfer (\d+): (ok|rejected)", out)}
    found = re.search(r"balances: (-?\d+) (-?\d+) (-?\d+) (-?\d+)", out)
    if len(ok) != len(transfers) or not found:
        return [f"the report is incomplete: {out!r}"]
    got = [int(x) for x in found.groups()]
    want = list(START)
    for k, (src, dst, amount) in enumerate(transfers):
        if ok[k]:
            want[src] -= amount
            want[dst] += amount
    problems = []
    if sum(got) != sum(START):
        problems.append(f"the bank's total changed: {sum(START)} -> {sum(got)} (balances {got})")
    if min(got) < 0:
        problems.append(f"an account went negative: {got}")
    if got != want and not problems:
        problems.append(f"the balances {got} don't match the accepted transfers (expected {want})")
    return problems


def fixed_tests(ctx):
    return [case("one transfer at a time", [(0, 1, 700)], inject={}),
            case("two from the same account", [(0, 1, 700), (0, 2, 600), (3, 0, 100)])]


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        ts = [(rng.randrange(4), rng.randrange(4), rng.choice([100, 300, 500, 800, 1000]))
              for _ in range(rng.randrange(2, 10))]
        out.append(case(f"random {i}: {len(ts)} transfers", ts, hidden=True))
    return out


def witness_test(w, ctx):
    if set(w) != {"schedule"} or not isinstance(w["schedule"], int) or w["schedule"] < 0:
        raise ValueError("the witness is a schedule number: `;! witness schedule = 7`")
    return case("witness", [(0, 1, 700), (0, 2, 600), (3, 0, 100)],
                inject={"schedule": w["schedule"]})
