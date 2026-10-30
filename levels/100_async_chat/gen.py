def room(clients, name, hidden=False, inject=None):
    """clients: {name: (join_ms, leave_ms, [(ms, text), ...])}; events ≥ 5 ms apart."""
    events = []                                   # (ms, who, what everyone else sees)
    for who, (join, leave, lines) in clients.items():
        events.append((join, who, f"* {who} joined\n"))
        events += [(t, who, f"{who}: {text}\n") for t, text in lines]
        events.append((leave, who, f"* {who} left\n"))
    events.sort()
    peers = []
    for who, (join, leave, lines) in clients.items():
        mine = [(t, "send", text) for t, text in lines]
        mine += [(t, "expect", seen) for t, other, seen in events
                 if other != who and join < t < leave]
        mine.sort(key=lambda e: e[0])
        steps = [{"send": f"{who}\n"}]
        for t, kind, text in mine:
            steps += [{"until": t * 1000}, {"send": text + "\n"}] if kind == "send" \
                else [{"expect": text}]
        steps += [{"until": leave * 1000}, {"close": True}]
        peers.append({"name": who, "connect": 7000, "at": join * 1000, "steps": steps})
    return {"name": name, "hidden": hidden,
            "inject": {"peers": peers, **(inject or {"schedule_sweep": {"count": 10}})},
            "expect": {"check": True, "stderr": ""}}


def check(test, m):
    problems = []
    leaked = [b for b in m.kernel.blocks.values() if not b["freed"]]
    if leaked:
        where = ", ".join(sorted({b["alloc"] for b in leaked}))
        problems.append(f"{len(leaked)} heap block(s) never freed (allocated at {where})")
    open_conns = sorted(fd for fd, f in m.kernel.fds.items() if f.kind == "conn")
    if open_conns:
        problems.append(f"sockets of clients that are gone are still open: fds {open_conns}")
    return problems


def slow_client(hidden=False):
    lines = [f"line {i:04d} " + "x" * 70 for i in range(1000)]
    peers = [
        {"name": "listener", "connect": 7000, "at": 0,
         "steps": [{"send": "listener\n"},
                   {"expect_lines": [f"talker: {ln}\n" for ln in lines], "ignore_prefix": "* "},
                   {"until": 2_000_000}, {"close": True}]},
        {"name": "slow", "connect": 7000, "at": 10_000,       # never reads a byte
         "steps": [{"send": "slow\n"}, {"until": 3_000_000}, {"close": True}]},
        {"name": "talker", "connect": 7000, "at": 20_000,
         "steps": [{"send": "talker\n"}, {"until": 30_000},
                   {"send": "".join(ln + "\n" for ln in lines)},
                   {"until": 2_500_000}, {"close": True}]},
    ]
    return {"name": "a client that never reads", "hidden": hidden, "inject": {"peers": peers},
            "expect": {"check": True, "stderr": ""}}


def cancelled(hidden=True):
    peers = []
    for i, who in enumerate(["ann", "bob", "cy"]):
        steps = [{"send": f"{who}\n"}]
        for k in range(3):
            steps += [{"until": 20_000 + 30_000 * k + 7_000 * i}, {"send": f"{who} {k}\n"},
                      {"drain": True}]
        steps += [{"until": 200_000 + 5_000 * i}, {"drain": True}, {"close": True}]
        peers.append({"name": who, "connect": 7000, "at": 1000 * i, "steps": steps})
    return {"name": "readers cancelled at every await", "hidden": hidden,
            "inject": {"peers": peers, "cancel_sweep": {"functions": ["reader"]}},
            "expect": {"check": True, "stderr": ""}}


def fixed_tests(ctx):
    return [
        room({"ann": (0, 200, [(30, "hello")]), "bob": (10, 200, [(60, "hi ann")])},
             "two people"),
        room({"ann": (0, 400, [(50, "anyone?"), (200, "bye bob")]),
              "bob": (20, 150, [(100, "me!")]),
              "cy": (120, 400, [(250, "did I miss anything")])}, "people come and go"),
        slow_client(),
    ]


def generate(rng, count, ctx):
    out = [cancelled(),
           {"name": "clients that never say their name", "hidden": True,
            "inject": {"peers": [
                {"name": "mute", "connect": 7000, "at": 0, "steps": [{"until": 50_000}, {"close": True}]},
                {"name": "half", "connect": 7000, "at": 0,
                 "steps": [{"send": "hal"}, {"until": 60_000}, {"close": True}]},
                {"name": "ann", "connect": 7000, "at": 5_000,
                 "steps": [{"send": "ann\n"}, {"until": 100_000}, {"close": True}]}]},
            "expect": {"check": True, "stderr": ""}}]
    for k in range(count):
        clients, used = {}, set()

        def slot(lo, hi):
            for _ in range(200):
                t = rng.randrange(lo, hi)
                if all(abs(t - u) >= 6 for u in used):
                    used.add(t)
                    return t
            return None
        for i in range(rng.randrange(2, 6)):
            join = slot(0, 300)
            leave = slot(join + 60, join + 500)
            if join is None or leave is None:
                continue
            lines = []
            for _ in range(rng.randrange(0, 4)):
                t = slot(join + 6, leave - 5)
                if t is not None:
                    lines.append((t, f"message {t} from user{i}"))
            clients[f"user{i}"] = (join, leave, sorted(lines))
        out.append(room(clients, f"random room {k}", hidden=True))
    return out
