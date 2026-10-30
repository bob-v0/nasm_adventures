def expected(events):
    """events: (time_us, source, text). Lines in the order they complete."""
    bufs, out = {"A": "", "B": ""}, ""
    for _, src, text in sorted(events, key=lambda e: e[0]):
        bufs[src] += text
        while "\n" in bufs[src]:
            line, bufs[src] = bufs[src].split("\n", 1)
            out += f"{src}: {line}\n"
    return out + "done\n"


def case(name, events, hidden=False):
    peers = []
    for fd, src in ((3, "A"), (4, "B")):
        steps, now = [], 0
        for t, s, text in sorted(e for e in events if e[1] == src):
            if t > now:
                steps.append({"sleep": t - now})
                now = t
            steps.append({"send": text})
        peers.append({"name": f"sensor {src}", "pipe": fd, "steps": steps})
    return {"name": name, "hidden": hidden, "inject": {"peers": peers},
            "expect": {"stdout": expected(events), "exit": 0, "end": "exited"}}


def fixed_tests(ctx):
    return [
        case("taking turns", [(0, "A", "a1\n"), (5000, "B", "b1\n"), (10000, "A", "a2\n"),
                              (15000, "B", "b2\n")]),
        case("B is faster", [(0, "A", "slow 1\n"), (40000, "A", "slow 2\n")] +
             [(5000 + 5000 * i, "B", f"fast {i}\n") for i in range(10)]),
        case("lines in pieces", [(0, "A", "tempera"), (4000, "B", "humidity 4"),
                                 (8000, "A", "ture 21.5\n"), (12000, "B", "0%\n")]),
    ]


def generate(rng, count, ctx):
    out = [case("one sensor says nothing", [(3000 * i, "B", f"only b {i}\n") for i in range(6)], True)]
    for k in range(count):
        events, t = [], 0
        for i in range(rng.randrange(4, 16)):
            t += rng.randrange(3000, 20000)
            src = rng.choice("AB")
            text = f"{src.lower()}{i} " + "x" * rng.randrange(0, 30)
            if rng.random() < 0.3:          # in two pieces
                cut = rng.randrange(1, len(text))
                events += [(t, src, text[:cut])]
                t += rng.randrange(3000, 9000)
                events += [(t, src, text[cut:] + "\n")]
            else:
                events.append((t, src, text + "\n"))
        out.append(case(f"random {k}", events, True))
    return out
