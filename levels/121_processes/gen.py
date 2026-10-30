COMMANDS = {   # path -> (what it prints, report line)
    "/bin/true": ("", "exited 0"),
    "/bin/false": ("", "exited 1"),
    "/bin/exit3": ("", "exited 3"),
    "/bin/hello": ("hello world\n", "exited 0"),
    "/bin/echo": ("\n", "exited 0"),
    "/bin/crash": ("", "killed by signal 11"),
    "/work/nope": ("", "exited 127"),
    "/work/notes.txt": ("", "exited 127"),
    "/etc": ("", "exited 127"),
}


def case(name, cmds, hidden=False):
    out, err, failed = "", "", 0
    for c in cmds:
        printed, report = COMMANDS[c]
        out += printed + f"{c}: {report}\n"
        if report.endswith("127"):
            err += f"{c}: cannot execute\n"
        failed += report != "exited 0"
    return {"name": name, "hidden": hidden, "userland": True,
            "argv": ["./solution"] + cmds, "env": {"HOME": "/home/player"},
            "files": {"/work/notes.txt": "not a program\n"},
            "expect": {"stdout": out, "stderr": err, "exit": failed, "check": True}}


def check(test, m):
    zombies = sorted(p for p in m.kernel.procs if p != m.proc.pid)
    if zombies:
        return [f"children never waited for (zombies): pids {zombies}"]
    return []


def fixed_tests(ctx):
    return [case("true and false", ["/bin/true", "/bin/false"]),
            case("a crash", ["/bin/hello", "/bin/crash", "/bin/exit3"]),
            case("not a program", ["/work/nope", "/bin/true"])]


def generate(rng, count, ctx):
    out = [case("no commands", []), case("every kind", list(COMMANDS), hidden=True)]
    for i in range(count):
        cmds = [rng.choice(list(COMMANDS)) for _ in range(rng.randrange(1, 7))]
        out.append(case(f"random {i}", cmds, hidden=True))
    return out
