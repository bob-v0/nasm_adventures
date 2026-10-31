"""Level 32: keys typed into the kernel, through the I/O APIC."""

import re


def keys_for(text):
    return [{" ": "spc", "\n": "ret"}.get(c, c) for c in text] + ["esc"]


def case(name, text, hidden=False):
    want = "ready\r\n" + text.replace("\n", "\r\n") + "\r\nbye\r\n"
    return {"name": name, "hidden": hidden,
            "inject": {"keys": keys_for(text), "ready": "ready\r\n"},
            "expect": {"serial": want, "check": True, "timeout": 12}}


def check(test, run, regs, screen, serial):
    pins = run.hmp("info pic")
    m = re.search(r"pin 1\s+0x[0-9a-f]+ dest=(\d+) vec=(\d+)\s+(\S+) (\S+)\s+(masked)?", pins)
    if not m:
        return []
    dest, vec, masked = int(m.group(1)), int(m.group(2)), m.group(5)
    if masked:
        return ["the I/O APIC's entry for IRQ 1 is still masked (bit 16)"]
    if vec != 0x41:
        return [f"the I/O APIC delivers IRQ 1 as vector {vec:#x}; the level asks for 0x41"]
    return []


def fixed_tests(ctx):
    return [case("hello", "hello world\nbye")]


def generate(rng, count, ctx):
    return [case(f"random {i}", "".join(rng.choice("abcdefghijklmnopqrstuvwxyz0123456789 \n")
                                        for _ in range(30)), True) for i in range(count)]
