import re


def case(name, jobs, hidden=False, sweep=True):
    t = {"name": name, "hidden": hidden, "mem": [{"sym": "njobs", "u64": jobs}],
         "expect": {"exit": 0, "stderr": "", "check": True, "jobs": jobs}}
    if sweep:
        t["inject"] = {"cancel_sweep": {}}
    return t


def check(test, m):
    out = bytes(m.stdout).decode("latin-1")
    found = re.search(r"done (\d+), cancelled (\d+), records (\d+)", out)
    if not found:
        return [f"no report line: {out!r}"]
    done, cancelled, records = map(int, found.groups())
    problems = []
    if done + cancelled != test.expect["jobs"]:
        problems.append(f"{test.expect['jobs']} jobs, but {done} done + {cancelled} cancelled")
    if records != done:
        problems.append(f"{records} records written for {done} finished jobs")
    leaked = [(a, b) for a, b in m.kernel.blocks.items() if not b["freed"]]
    if leaked:
        where = ", ".join(sorted({b["alloc"] for _, b in leaked}))
        problems.append(f"{len(leaked)} buffer(s) never freed (allocated at {where})")
    return problems


def fixed_tests(ctx):
    return [case("nobody cancelled", 4, sweep=False),
            case("cancelled at every await", 3)]


def generate(rng, count, ctx):
    return [case(f"{n} jobs, cancelled at every await", n, hidden=True)
            for n in rng.sample(range(1, 9), count)]
