import string


def client(name, chunks, at, ending="close"):
    """chunks: list of (text, sleep_us before sending it)."""
    steps = []
    for text, pause in chunks:
        if pause:
            steps.append({"sleep": pause})
        steps += [{"send": text}, {"expect": text}]
    if ending == "shutdown":                   # half-close: the server reads EOF, closes
        steps += [{"shutdown": True}, {"expect_eof": True}]
    else:
        steps.append({"close": True})
    return {"name": name, "connect": 7000, "at": at, "steps": steps}


def case(name, peers, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"peers": peers},
            "expect": {"check": True}}


def check(test, m):
    problems = []
    calls = {str(s).split("(")[0] for s in m.syscalls}
    if "epoll_wait" not in calls and "epoll_pwait" not in calls:
        problems.append("the server must wait for events with epoll_wait")
    left = sorted(fd for fd, f in m.kernel.fds.items() if f.kind == "conn")
    if left:
        problems.append(f"connections still open after their clients left: fds {left} "
                        "(close a client when read returns 0)")
    return problems


def fixed_tests(ctx):
    return [
        case("one client", [client("ann", [("hello\n", 0), ("again\n", 2000)], at=0)]),
        case("two at once", [client("ann", [("a1\n", 0), ("a2\n", 30_000)], at=0),
                             client("bob", [("b1\n", 0), ("b2\n", 5000), ("b3\n", 5000)], at=1000)]),
        case("a client hangs up its side", [client("cy", [("bye now\n", 0)], at=0, ending="shutdown")]),
    ]


def generate(rng, count, ctx):
    out = []
    for k in range(count):
        peers = []
        for i in range(rng.randrange(5, 40)):
            chunks = []
            for _ in range(rng.randrange(1, 5)):
                text = "".join(rng.choice(string.ascii_letters + " ") for _ in range(rng.randrange(1, 60)))
                chunks.append((text + rng.choice(["\n", ""]), rng.choice([0, 0, 500, 20_000])))
            peers.append(client(f"client {i + 1}", chunks, at=rng.randrange(0, 100_000),
                                ending=rng.choice(["close", "shutdown"])))
        out.append(case(f"{len(peers)} clients", peers, True))
    return out
