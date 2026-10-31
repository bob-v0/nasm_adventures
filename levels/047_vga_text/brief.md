# Level 47 — VGA Text Mode

*The BIOS prints one character per interrupt. The screen itself is just memory.*

## Lesson: the screen is memory

In text mode, the VGA card shows a grid of 80 × 25 **cells**, stored in memory at
physical **B8000** (segment 0xB800). Writing a byte there changes the screen at once.
Devices that you control by writing memory like this use **memory-mapped I/O**.

Each cell is two bytes: the character, then its **attribute** (its colours):

```
  byte 0: the character (code page 437)     byte 1: the attribute
                                              7    6 5 4    3 2 1 0
                                              blink background foreground
```

![A cell: the character byte and the attribute byte's bit fields](cell.svg)

Cell (row, column) is at offset `row × 160 + column × 2` (160 = 80 cells × 2 bytes).

| colour | value | | colour | value |
|---|---|---|---|---|
| black | 0 | | dark grey | 8 |
| blue | 1 | | light blue | 9 |
| green | 2 | | light green | A |
| cyan | 3 | | light cyan | B |
| red | 4 | | light red | C |
| magenta | 5 | | pink | D |
| brown | 6 | | yellow | E |
| light grey | 7 | | white | F |

Example: attribute 0x1E is yellow (E) on blue (1). Backgrounds only go from 0 to 7,
because bit 7 is blink.

**Code page 437**, the PC's original character set, has line and block characters
above 127: `C9 ╔  CD ═  BB ╗  BA ║  C8 ╚  BC ╝`, `C4 ─  B3 │`, `DB █  B0 ░`.

## Lesson: filling memory

`stosw` stores ax at es:di and advances di by 2 (if the direction flag is clear: `cld`).
`rep stosw` does it cx times, so one instruction can fill the whole screen. With al =
the character and ah = the attribute, each stosw draws one cell.

## Lesson: the cursor

The blinking cursor isn't in video memory: it's in the VGA's CRT controller, reached
through I/O **ports** (level 46). Its position is row × 80 + column. Write register
number 0x0F (the position's low byte) to port 0x3D4, then the value to port 0x3D5; same
for register 0x0E (the high byte). Not graded here; try it in QEMU (`-display curses`).

## Gate

Draw the exact screen described in the starter by writing video memory, then halt. No
`int` instructions (the tests check). Every cell's character and attribute must match.
