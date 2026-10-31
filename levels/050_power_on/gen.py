def fixed_tests(ctx):
    return [{"name": "power on", "expect": {"check": True, "regs": {"ax": 0xB007, "dl": 0x80,
                                                                       "si": 0xF000, "di": 0xE05B}}}]


def check(test, run, regs, screen, serial):
    bx = regs["bx"]
    if run.read(bx, 2) != b"\x07\xb0":
        return [f"bx = {bx:#06x}, but the word there isn't 0xB007: bx must be the address of your "
                "magic word (with org 0x7C00, the label's value)"]
    if not 0x7C00 <= bx < 0x7E00:
        return [f"bx = {bx:#06x} isn't in your boot sector (0x7C00-0x7DFF)"]
    return []
