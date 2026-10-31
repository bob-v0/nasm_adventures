def fixed_tests(ctx):
    return [{"name": "the switch", "expect": {"check": True,
                                              "serial": "Hello from protected mode!\r\n"}}]


def check(test, run, regs, screen, serial):
    out = []
    if not regs["cr0"] & 1:
        return ["cr0 bit 0 (PE) is clear: still in real mode"]
    cs_attr = None
    text = run.hmp("info registers")
    import re
    m = re.search(r"^CS =([0-9a-f]{4}) ([0-9a-f]{8}) ([0-9a-f]{8}) ([0-9a-f]{8})", text, re.M)
    if m:
        cs_attr = int(m.group(4), 16)
    if regs["cs"] != 0x08:
        out.append(f"cs = {regs['cs']:#06x}: the far jump should load the code selector 0x08")
    elif cs_attr is not None and not cs_attr >> 22 & 1:
        out.append("cs is a 16-bit segment (D = 0): the code descriptor needs D = 1 for 32-bit code")
    for seg in ("ds", "es", "ss"):
        if regs[seg] != 0x10:
            out.append(f"{seg} = {regs[seg]:#06x}: load the data selector 0x10 into it")
            break
    if not any("PROTECTED MODE" in row for row in screen):
        out.append("the screen doesn't show PROTECTED MODE (written to 0xB8000)")
    return out
