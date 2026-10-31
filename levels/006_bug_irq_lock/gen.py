"""Level 6: keys typed while the kernel works. Each key is logged by the keyboard's
interrupt handler, under the same lock the kernel's work holds almost all the time."""


def keys_for(text):
    return [{" ": "spc"}.get(c, c) for c in text] + ["esc"]


def case(name, text, hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"keys": keys_for(text), "ready": "ready\r\n"},
            "expect": {"check": True, "text": text, "timeout": 10}}


def check(test, run, regs, screen, serial):
    lines = serial.decode("latin-1").split("\r\n")
    keys = [l[len("key: "):] for l in lines if l.startswith("key: ")]
    want = [c for c in test.expect["text"]]
    problems = []
    if keys != want:
        problems.append(f"the keys typed: {want}; the log has {keys}" +
                        (" (then nothing: the kernel froze?)" if len(keys) < len(want) else ""))
    if "bye" not in lines:
        problems.append("no `bye` after Esc: the kernel stopped answering")
    if any(l and not (l.startswith(("key: ", "working: round ")) or l in ("ready", "bye")) for l in lines):
        bad = [l for l in lines if l and not (l.startswith(("key: ", "working: round ")) or l in ("ready", "bye"))]
        problems.append(f"lines that are two lines mixed together: {bad[:2]}")
    return problems


def fixed_tests(ctx):
    return [case("a few keys", "hello"), case("a sentence", "the quick brown fox")]


def generate(rng, count, ctx):
    return [case(f"random {i}", "".join(rng.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(25)), True)
            for i in range(count)]
