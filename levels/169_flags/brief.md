# Level 169 — The Flags Register

*Every result leaves a trace. Learn to read it before you need it.*

## Lesson: RFLAGS

After most arithmetic, the CPU sets bits in the **RFLAGS** register that describe
the result:

| Flag | Name | Set when… |
|---|---|---|
| **CF** | carry | the result didn't fit as an **unsigned** number (a carry out of the top bit, or a borrow in `sub`) |
| **ZF** | zero | the result is zero |
| **SF** | sign | the top bit of the result is 1 (negative, if you read it as signed) |
| **OF** | overflow | the result didn't fit as a **signed** number (e.g. two positives added up to a negative) |
| PF | parity | the low byte of the result has an even number of 1 bits |
| AF | adjust | a carry out of bit 3 (for old decimal arithmetic) |

The flags come from the operand **size**: `add al, 1` sets flags from an 8-bit
result, `add rax, 1` from a 64-bit one. `mov` never changes flags. `inc` and `dec`
change ZF, SF and OF but **not CF**, a quirk that matters in the next level.

Flags are how the CPU makes decisions: every conditional jump (level 167) reads them.

## Gate, part 1: predict

For each pair of instructions, predict CF, ZF, SF and OF after the second one:

| # | Instructions | |
|---|---|---|
| 1 | `mov al, 0xFF` → `add al, 1` | 8-bit |
| 2 | `mov al, 0x7F` → `add al, 1` | 8-bit |
| 3 | `mov al, 0x80` → `sub al, 1` | 8-bit |
| 4 | `mov al, 0` → `sub al, 1` | 8-bit |
| 5 | `mov eax, 5` → `sub eax, 5` | 32-bit |
| 6 | `mov rax, -1` → `add rax, -1` | 64-bit |
| 7 | `mov al, 0x80` → `add al, 0x80` | 8-bit |
| 8 | `mov al, 0x40` → `add al, 0x40` | 8-bit |

Write your answers into `answers` in the starter: four bytes per operation, in the
order CF, ZF, SF, OF, each 0 or 1.

**Predict first, then check.** Copy an operation into your code, step over it in the
debugger, and read the flags row (set flags are highlighted). Being wrong in the
debugger is free.

## Gate, part 2: command the flags

When your code finishes, the flags must be **CF=1, ZF=1, SF=0, OF=1**. One of the
eight operations above does exactly that.
