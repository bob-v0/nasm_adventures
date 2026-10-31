# Level 169 — The Flags Register

*Every result leaves a trace. Learn to read it before you need it.*

## Lesson: RFLAGS

After most arithmetic, the CPU sets single-bit **flags** in the **RFLAGS** register
that describe the result. The instruction doesn't decide anything; it just leaves
notes about what happened, and later instructions can read them:

| Flag | Name | Set when… |
|---|---|---|
| **CF** | carry | the result didn't fit as an **unsigned** number (a carry out of the top bit, or a borrow in `sub`) |
| **ZF** | zero | the result is zero |
| **SF** | sign | the top bit of the result is 1 (negative, if you read it as signed) |
| **OF** | overflow | the result didn't fit as a **signed** number (e.g. two positives added up to a negative) |
| PF | parity | the low byte of the result has an even number of 1 bits |
| AF | adjust | a carry out of bit 3 (for old decimal arithmetic) |

A worked example, in 8 bits:

```
mov al, 200        ; 1100_1000   (as signed: -56)
add al, 100        ; 0110_0100   (as signed: +100)
                   ; true sum 300 doesn't fit in 8 bits: al = 300 - 256 = 44
CF = 1             ; unsigned: 200 + 100 = 300 > 255, a carry fell off the top
ZF = 0             ; 44 is not zero
SF = 0             ; top bit of 0010_1100 is 0
OF = 0             ; signed: -56 + 100 = 44, which fits in -128..127
```

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
