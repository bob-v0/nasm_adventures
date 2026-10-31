"""Level 47: the exact screen to draw."""

BG, BORDER, INSIDE, STATUS = 0x17, 0x1E, 0x3F, 0x70
LEFT, TOP, RIGHT, BOTTOM = 20, 8, 59, 16
TITLE, TITLE_ROW = "NASM ADVENTURES", 12
STATUS_TEXT = " Level 47: VGA text mode"


def expected() -> bytes:
    cells = [[(0x20, BG) for _ in range(80)] for _ in range(25)]
    for y in range(TOP, BOTTOM + 1):
        for x in range(LEFT, RIGHT + 1):
            if (y, x) == (TOP, LEFT):
                c = 0xC9
            elif (y, x) == (TOP, RIGHT):
                c = 0xBB
            elif (y, x) == (BOTTOM, LEFT):
                c = 0xC8
            elif (y, x) == (BOTTOM, RIGHT):
                c = 0xBC
            elif y in (TOP, BOTTOM):
                c = 0xCD
            elif x in (LEFT, RIGHT):
                c = 0xBA
            else:
                cells[y][x] = (0x20, INSIDE)
                continue
            cells[y][x] = (c, BORDER)
    start = LEFT + 1 + (RIGHT - LEFT - 1 - len(TITLE)) // 2
    for k, ch in enumerate(TITLE):
        cells[TITLE_ROW][start + k] = (ord(ch), INSIDE)
    for x in range(80):
        cells[24][x] = (ord(STATUS_TEXT[x]) if x < len(STATUS_TEXT) else 0x20, STATUS)
    return bytes(b for row in cells for c, a in row for b in (c, a))


def fixed_tests(ctx):
    return [{"name": "the screen", "expect": {"check": True, "show_screen": False}}]


def check(test, run, regs, screen, serial):
    want, got = expected(), run.read(0xB8000, 4000)
    for i in range(0, 4000, 2):
        if want[i:i + 2] != got[i:i + 2]:
            y, x = divmod(i // 2, 80)
            return [f"row {y}, column {x}: expected character {want[i]:#04x} with attribute "
                    f"{want[i + 1]:#04x}, got {got[i]:#04x} with {got[i + 1]:#04x}",
                    "your screen:\n" + "\n".join("    |" + r for r in screen)]
    return []


def audit(build):
    from ring.checks import disassemble
    ints = [ops for _, mn, ops in disassemble(build) if mn == "int"]
    return [("draws by writing video memory (no int)", not ints,
             f"found int {', '.join(ints)}" if ints else "")]
