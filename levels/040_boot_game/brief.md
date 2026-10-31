# Level 40 — Boot Sector Game ★

*No operating system, no libraries, no files: 512 bytes and a PC. People have fit chess,
Tetris and a BASIC interpreter into that. You'll fit a puzzle.*

## The game

A box-pushing puzzle. The map is in the starter:

| character | square |
|---|---|
| `#` | wall |
| (space) | floor |
| `.` | target |
| `$` | box |
| `*` | box on a target |
| `@` | you |
| `+` | you on a target |

The arrow keys move you one square, unless a wall is in the way. Walking into a box
pushes it one square, unless a wall or another box is behind it. Every move that happens
counts (pushes too); blocked ones don't. Push all three boxes onto targets to win.

The game draws the map at the top left of the screen and, on the last row (row 24),
the move count: `Moves: 12`. When the last box lands, row 24 says
`You win in 38 moves!` and the game halts (`cli`, `hlt`).

## Everything in the arc

- **Boot sector** (50): 512 bytes, `org 0x7C00`, the signature. Everything must fit,
  map included: the game checks the size.
- **Segments** (49, 48): set them yourself; this game is tested under SeaBIOS.
- **The screen** (47): write video memory, row by row.
- **The keyboard** (43): your own controller code, or the BIOS. `int 0x16` with ah = 0
  waits for a key and returns its scancode in ah. (With interrupts on, the BIOS's IRQ 1
  handler is what fills its buffer: level 42.) Up 0x48, down 0x50, left 0x4B,
  right 0x4D.
- **Data in the code** (all of it): the map is bytes in your sector, and the sector is in
  RAM. Change it in place.

## Size tricks

`lodsb`/`stosw` are one byte each; so is `xchg ax, reg`; `loop` saves a `dec`/`jnz`.
Keep values in registers instead of variables, and use one routine for both status
lines (the number goes in the middle). The reference solution is about 300 bytes, so
there's room.

## Gate

The game, in one sector of at most 512 bytes. The game tries several key sequences:
every one must end with the right map and row 24, and the winning ones with the winning
line and a halt. Keys after the win change nothing.
