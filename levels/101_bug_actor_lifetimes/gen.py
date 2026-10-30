def chat(clients, hidden=False, name="chat"):
    """clients: {name: (join_ms, leave_ms, [(ms, text), ...])}. Messages are ≥ 5 ms apart
    from joins/leaves, so the expected deliveries are unambiguous."""
    said = sorted((t, who, text) for who, (_, _, lines) in clients.items() for t, text in lines)
    peers = []
    for who, (join, leave, lines) in clients.items():
        events = [(t, "send", text) for t, text in lines]
        events += [(t, "expect", text) for t, other, text in said
                   if other != who and join < t < leave]
        events.sort(key=lambda e: e[0])
        steps = []
        for t, kind, text in events:
            if kind == "send":
                steps += [{"until": t * 1000}, {"send": text}]
            else:
                steps.append({"expect": text})
        steps += [{"until": leave * 1000}, {"close": True}]
        peers.append({"name": who, "connect": 7000, "at": join * 1000, "steps": steps})
    return {"name": name, "hidden": hidden,
            "inject": {"peers": peers, "schedule_sweep": {"count": 25}},
            "expect": {"check": True}}


def check(test, m):
    leaked = [b for b in m.kernel.blocks.values() if not b["freed"]]
    problems = []
    if leaked:
        where = ", ".join(sorted({b["alloc"] for b in leaked}))
        problems.append(f"{len(leaked)} message(s) never freed (allocated at {where}): the "
                        "receiver of a message owns it and must free it")
    open_conns = sorted(fd for fd, f in m.kernel.fds.items() if f.kind == "conn")
    if open_conns:
        problems.append(f"sockets of clients that left are still open: fds {open_conns}")
    return problems


def race(name="a leave and a message at the same moment", hidden=False):
    """bob leaves exactly when ann speaks: ann's text may still be on its way to him."""
    t = chat({"ann": (0, 300, [(50, "is bob still here?\n")]),
              "bob": (5, 50, []),
              "cy": (10, 300, [])}, name=name, hidden=hidden)
    for p in t["inject"]["peers"]:
        if p["name"] == "bob":
            p["steps"] = [{"until": 50_000}, {"close": True}]    # the very moment ann speaks
    return t


def fixed_tests(ctx):
    return [
        chat({"ann": (0, 200, [(30, "hello from ann\n")]),
              "bob": (5, 200, [(60, "hi ann\n")])}, name="two people"),
        race(),
    ]


def generate(rng, count, ctx):
    out = []
    for k in range(count):
        clients = {}
        t = 0
        for i in range(rng.randrange(3, 9)):
            join = rng.randrange(0, 200)
            leave = join + rng.randrange(100, 600)
            clients[f"user{i}"] = [join, leave, []]
        slots = sorted(rng.sample(range(5, 900, 7), 12))
        for s in slots:
            who = rng.choice([w for w, (j, l, _) in clients.items()] )
            j, l, lines = clients[who]
            if j + 5 < s < l - 5 and all(abs(s - x) >= 5 for c in clients.values() for x in c[:2]):
                lines.append((s, f"{who} says {s}\n"))
        out.append(chat({w: tuple(v) for w, v in clients.items()}, hidden=True,
                        name=f"random room {k}"))
    return out + [race("leaving while being talked to, again", hidden=True)]


def witness_test(w, ctx):
    if set(w) != {"schedule"} or not isinstance(w["schedule"], int) or w["schedule"] < 0:
        raise ValueError("the witness is a schedule number: `;! witness schedule = 7`")
    t = race("witness")
    t["inject"] = {"peers": t["inject"]["peers"], "schedule": w["schedule"]}
    return t
