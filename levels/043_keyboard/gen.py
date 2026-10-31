"""Level 43: keys typed into your line editor (QEMU key names)."""


def keys_for(text):
    out = []
    for ch in text:
        if ch == " ":
            out.append("spc")
        elif ch == "\b":
            out.append("backspace")
        elif ch.isupper():
            out.append("shift-" + ch.lower())
        else:
            out.append(ch)
    return out + ["ret"]


def result(text):
    line = []
    for ch in text:
        if ch == "\b":
            if line:
                line.pop()
        elif len(line) < 70:
            line.append(ch)
    return "".join(line)


def case(name, text, hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"keys": keys_for(text), "ready": "> "},
            "expect": {"serial": f"> {result(text)}\r\n", "timeout": 12}}


def fixed_tests(ctx):
    return [case("hello world", "hello world"), case("typos", "helo\b\blo there"),
            case("Shift", "Hello World 2025")]


def generate(rng, count, ctx):
    out = [case("backspace on an empty line", "\b\bok", True)]
    for i in range(count):
        text = "".join(rng.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJ0123456789   \b") for _ in range(25))
        out.append(case(f"random typing {i}", text, True))
    return out


def audit(build):
    from ring.checks import disassemble
    ins = disassemble(build)
    kb = [ops for _, mn, ops in ins if mn == "int" and ops.lower() in ("0x16", "0x9", "9", "0x09")]
    return [("reads the keyboard controller itself (no int 0x16)", not kb, ""),
            ("uses in", any(mn == "in" for _, mn, _ in ins), "")]
