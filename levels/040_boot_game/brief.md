# Level 40 — Boot Sector Game ★

*No operating system, no libraries, no files: 512 bytes and a PC. People have fit chess,
Tetris and a BASIC interpreter into that. You'll fit a puzzle.*

## The game

A box-pushing puzzle. The map is in the starter: walls `#`, three boxes `$`, three
targets `.`, and you, `@`. The arrow keys move you; walking into a box pushes it, if the
square behind it is free. A box on a target is drawn `*`, you on a target `+`. Push every
box onto a target to win.

The game draws the map at the top left of the screen, a count of moves on the last row
(`Moves: 12`), and when the last box lands, `You win in 38 moves!`, then halts.

## Everything in the arc

- **Boot sector** (50): 512 bytes, `org 0x7C00`, the signature. Everything must fit,
  map included: the game checks the size.
- **Segments** (49, 48): set them yourself; this game is tested under SeaBIOS.
- **The screen** (47): write video memory, row by row.
- **The keyboard** (43): your own controller code, or the BIOS: `int 0x16` with ah = 0
  waits for a key and returns its scancode in ah (with interrupts on, the BIOS's IRQ 1
  handler is what fills its buffer, level 42). Up 0x48, down 0x50, left 0x4B, right 0x4D.
- **Data in the code** (all of it): the map is bytes in your sector, which is RAM. Change
  it in place.

## Size tricks

`lodsb`/`stosw` are one byte each; `xchg ax, reg` is one byte; `loop`; keeping values in
registers instead of variables; one routine for both status lines (the number in the
middle). The reference solution is about 300 bytes, so there's room.

## Gate

The game, in one sector: every key sequence the game tries ends with the right screen,
and the winning ones with the winning line and a halt.
