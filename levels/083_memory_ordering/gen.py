import re

INJECT = {"tso": True, "quantum": 10}


def case(name, variant, inject, hidden=False):
    return {"name": name, "hidden": hidden, "argv": ["./litmus", variant],
            "inject": {**INJECT, **inject}, "expect": {"exit": 0, "check": True,
                                                         "variant": variant}}


def check(test, m):
    out = bytes(m.stdout).decode()
    found = re.match(r"r1=(\d) r2=(\d)", out)
    if not found:
        return [f"unexpected output {out!r}"]
    r1, r2 = int(found.group(1)), int(found.group(2))
    if (r1, r2) == (0, 0) and test.expect["variant"] == "fenced":
        return ["both threads read 0: the fenced version still lets a load pass the store "
                "before it"]
    if (r1, r2) not in ((0, 0), (0, 1), (1, 0), (1, 1)):
        return [f"r1 = {r1}, r2 = {r2}: each should be 0 or 1"]
    return []


def fixed_tests(ctx):
    return [case("plain, one schedule", "plain", {"schedule": 0}),
            case("fenced, many schedules", "fenced", {"schedule_sweep": {"count": 60}})]


def generate(rng, count, ctx):
    return [case("fenced, more schedules", "fenced", {"schedule_sweep": {"count": 60}, "quantum": 6},
                 hidden=True)]


def audit(build, level):
    """The witness: under that schedule, the plain version must show r1 = r2 = 0."""
    from ring.checks import parse_witness, run_test
    from ring.level import TestCase
    w = parse_witness(build.source.read_text()) or {}
    if set(w) != {"schedule"}:
        return [("a witness schedule where both threads read 0", False,
                 "add a line `;! witness schedule = N`")]
    t = TestCase.from_dict(case("witness", "plain", {"schedule": w["schedule"]}))
    _, m = run_test(level, build, t)
    out = bytes(m.stdout).decode() if m else ""
    ok = out.startswith("r1=0 r2=0")
    return [(f"witness (schedule {w['schedule']}): both threads read 0", ok,
             "" if ok else f"with that schedule the plain version printed {out.strip()!r}")]
