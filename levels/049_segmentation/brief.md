# Level 49 — Segmentation

*The 8086 had 16-bit registers and a 20-bit address bus. Segments are how Intel got from
one to the other, and every x86 still starts with them.*

## Lesson: segment × 16 + offset

A real-mode address is two 16-bit numbers, **segment:offset**, and the physical address
is `segment × 16 + offset`: 20 bits, one megabyte. A segment register picks a 64 KiB
window starting at any multiple of 16 (a "paragraph"), and the offset picks the byte in
it. So the same byte has many names:

| segment:offset | physical |
|---|---|
| 0000:7C00 | 07C00 |
| 07C0:0000 | 07C00 |
| 0700:0C00 | 07C00 |
| F000:FFF0 | FFFF0 (the reset vector) |

Which segment register an access uses depends on the instruction: code (ip) uses **cs**,
the stack (push, pop, [bp...]) **ss**, most data **ds**, and the string instructions'
destination (stosb, movsb) **es**. An override changes it: `mov al, [es:bx]`.

Segment registers can't be loaded with an immediate: `mov ax, 0xF000` / `mov ds, ax`.
And cs only changes with a far jump, call or return: `jmp 0x07C0:label`.

## Lesson: far pointers

A **far pointer** stores both halves: a word with the offset, then a word with the
segment. `lds si, [mem]` loads si from the first and ds from the second in one
instruction (`les` uses es). The game has put a note somewhere in memory and a far
pointer to it at 0000:0500, a free spot just after the BIOS's data area.

## Lesson: the BIOS's services

The BIOS doesn't only boot: it leaves an interrupt table of services. `int 0x10` is
video: with ah = 0x0E ("teletype"), it prints the character in al at the cursor,
handling 13 (carriage return) and 10 (line feed). Level 46 does the same without the BIOS.

## Gate

Print `Hello, segments!`, the note, and `BIOS date: ` with the 8 characters at F000:FFF5,
each on its own line.
