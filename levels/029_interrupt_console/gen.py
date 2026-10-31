"""Level 29: lines typed on the keyboard and into COM2 at the same time, with the APIC timer
running. Each source's lines must come out whole and in order; the two may interleave."""

import re

KEYS = "abcdefghijklmnopqrstuvwxyz0123456789 "
SERIAL = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,:;!?-+*/=()"


def keys_for(text):
    return [{" ": "spc", "\n": "ret", "\b": "backspace"}.get(c, c) for c in text]


def edited(text):
    """The lines that come out of `text` after its backspaces."""
    lines, cur = [], ""
    for c in text:
        if c in "\n\r":
            lines.append(cur)
            cur = ""
        elif c in "\b\x7f":
            cur = cur[:-1]
        else:
            cur += c
    return lines


def case(name, typed, sent, hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"keys": keys_for(typed + "bye\n"), "com2": sent + "bye\r",
                       "ready": "ready\r\n", "sample": ["ticks"]},
            "expect": {"check": True, "timeout": 30,
                       "lines": {"kbd": edited(typed + "bye\n"),
                                 "com2": edited(sent + "bye\r")}}}


def check(test, run, regs, screen, serial):
    text = serial.decode("latin-1")
    if not text.startswith("ready\r\n"):
        return [f"the output should start with `ready`; it starts {text[:30]!r}"]
    body = text[len("ready\r\n"):]
    lines = body.split("\r\n")
    if lines and lines[-1] == "":
        lines.pop()
    problems = []
    if not lines or lines[-1] != "bye":
        problems.append("the output should end with `bye` once both sources said `bye`"
                        + (f"; its last line: {lines[-1]!r}" if lines else "; nothing came after ready"))
    else:
        lines.pop()
    got = {"kbd": [], "com2": []}
    for line in lines:
        m = re.match(r"(kbd|com2): (.*)$", line, re.S)
        if not m:
            problems.append(f"a line that isn't `kbd: ...` or `com2: ...`: {line!r}")
            break
        got[m.group(1)].append(m.group(2))
    for src, want in test.expect["lines"].items():
        g = got[src]
        for k, (w, x) in enumerate(zip(want, g)):
            if w != x:
                problems.append(f"{src} line {k + 1}: expected {w!r}, got {x!r}")
                break
        else:
            if len(g) != len(want):
                problems.append(f"{src}: {len(want)} lines were typed, {len(g)} came out"
                                + (f" (next expected: {want[len(g)]!r})" if len(g) < len(want) else ""))
    if problems:
        return problems
    # the timer: 100 ticks per (virtual) second since `ready`
    if "ticks" not in run.symbols:
        return ["`ticks` should be a global label: the dword the timer interrupt increments"]
    start, t0 = run.samples.get("ticks", 0), run.samples.get("time")
    ticks = int.from_bytes(run.read(run.symbols["ticks"], 4), "little") - start
    t1 = run.virtual_seconds()
    if t0 is None or t1 is None:
        return []
    seconds = t1 - t0
    # (the clock it's compared with is QEMU's, read from outside: it drifts on a busy
    # machine; this catches a timer that's off, or off by an order of magnitude)
    if seconds >= 4 and not 0.5 <= ticks / (seconds * 100) <= 2.0:
        return [f"the timer counted {ticks} ticks in about {seconds} seconds: it should tick "
                "100 times a second"]
    if seconds < 4 and ticks == 0:
        return ["`ticks` never moved: is the APIC timer running?"]
    return []


def _line(rng, alphabet, n):
    return "".join(rng.choice(alphabet) for _ in range(n)).strip() or "x"


def fixed_tests(ctx):
    return [case("hello", "hello world\nls\n", "Hello, COM2!\rstatus\r"),
            case("editing", "helo\b\blo there\n\b\bok\n", "typo\x7f\x7fpe\rabc\x7f\x7f\x7f\r")]


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        typed = "".join(_line(rng, KEYS, rng.randint(1, 15)) + "\n" for _ in range(3))
        sent = "".join(_line(rng, SERIAL, rng.randint(1, 40)) + "\r" for _ in range(4))
        out.append(case(f"random {i}", typed, sent, True))
    return out
