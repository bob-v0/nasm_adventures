def check(test, m):
    """1..20 in order, and exactly one complete "signal" line per delivered signal."""
    text = bytes(m.stdout).decode("latin-1")
    if not text.endswith("\n"):
        return [f"the output doesn't end with a complete line: {text[-30:]!r}"]
    lines = text[:-1].split("\n")
    delivered = sum("SIGUSR1 delivered" in str(s) for s in m.syscalls)
    numbers = [ln for ln in lines if ln != "signal"]
    problems = []
    if numbers != [str(i) for i in range(1, 21)]:
        bad = next((ln for i, ln in enumerate(numbers) if ln != str(i + 1)), "(missing lines)")
        problems.append(f"the numbers are wrong: first bad line {bad!r} in {text!r}")
    if lines.count("signal") != delivered:
        problems.append(f"{delivered} signal(s) delivered but {lines.count('signal')} 'signal' line(s) printed")
    return problems


def fixed_tests(ctx):
    return [{"name": "no signal", "expect": {"check": True, "exit": 0}},
            {"name": "SIGUSR1 at every possible moment",
             "inject": {"signal_sweep": {"sig": 10, "after_syscall": "rt_sigaction", "tail": 12}},
             "expect": {"check": True, "exit": 0}}]
