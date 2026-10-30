IDLE = 5_000_000          # µs
SLACK = 200_000


def chat(name, at, messages, then="close"):
    """messages: (pause_us, text). A pause of IDLE or more gets the client cut off."""
    steps = []
    for pause, text in messages:
        if pause >= IDLE:
            steps += [{"expect": "timeout\n", "after": IDLE, "within": IDLE + SLACK},
                      {"expect_eof": True}]
            return {"name": name, "connect": 7000, "at": at, "steps": steps}
        if pause:
            steps.append({"sleep": pause})
        steps += [{"send": text}, {"expect": text}]
    if then == "idle":
        steps += [{"expect": "timeout\n", "after": IDLE, "within": IDLE + SLACK},
                  {"expect_eof": True}]
    else:
        steps.append({"close": True})
    return {"name": name, "connect": 7000, "at": at, "steps": steps}


def case(name, peers, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"peers": peers}, "expect": {"check": True}}


def check(test, m):
    calls = {str(s).split("(")[0] for s in m.syscalls}
    problems = []
    if "timerfd_settime" not in calls:
        problems.append("use a timerfd (timerfd_create, timerfd_settime) for the timeouts")
    left = sorted(fd for fd, f in m.kernel.fds.items() if f.kind == "conn")
    if left:
        problems.append(f"connections still open after their clients left: fds {left}")
    return problems


def fixed_tests(ctx):
    return [
        case("a quick client", [chat("ann", 0, [(0, "hi\n")])]),
        case("a client that goes quiet", [chat("bob", 0, [(0, "hello\n")], then="idle")]),
        case("one quiet, one busy", [
            chat("quiet", 0, [], then="idle"),
            chat("busy", 0, [(0, "1\n"), (3_000_000, "2\n"), (4_500_000, "3\n"),
                             (4_900_000, "4\n")])]),
    ]


def generate(rng, count, ctx):
    out = []
    for k in range(count):
        peers = []
        for i in range(rng.randrange(3, 12)):
            msgs = [(rng.choice([0, 1_000_000, 4_800_000, 6_000_000, rng.randrange(0, 4_900_000)]),
                     f"msg {j}\n") for j in range(rng.randrange(0, 5))]
            peers.append(chat(f"client {i + 1}", rng.randrange(0, 3_000_000), msgs,
                              then=rng.choice(["close", "idle"])))
        out.append(case(f"{len(peers)} clients", peers, True))
    return out
