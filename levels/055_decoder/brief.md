# Level 55 — Decoder

*x86 instructions are 1 to 15 bytes long, and nothing marks where one ends. Before a CPU
can do anything else it has to find out, 4 to 6 instructions per cycle.*

## Lesson: finding the length

Level 57's shape, read from left to right:

1. **Legacy prefixes**, any number: `66 67 F0 F2 F3 2E 3E 26 64 65 36`. Only 66 changes the
   length (16-bit immediates).
2. **REX** (40-4F) right before the opcode. Only W matters here (64-bit immediates for
   B8+r).
3. **Opcode**: one byte, or `0F` + one, or `0F 38` / `0F 3A` + one.
4. **ModRM**, if the opcode has one; then **SIB** and **displacement** as ModRM says:

   | mod | r/m ≠ 4, 5 | r/m = 4 (SIB) | r/m = 5 |
   |---|---|---|---|
   | 0 | — | SIB (+4 if SIB.base = 5) | disp32 (rip-relative) |
   | 1 | disp8 | SIB + disp8 | disp8 |
   | 2 | disp32 | SIB + disp32 | disp32 |
   | 3 | — (registers) | — | — |

5. **Immediate**, as the opcode says.

## The subset

| bytes | ModRM | immediate |
|---|---|---|
| 00-03, 08-0B, ..., 38-3B (add ... cmp) | yes | |
| 04, 0C, ..., 3C / 05, 0D, ..., 3D (al, imm8 / eax, imm) | | ib / iz |
| 50-5F, 90-99, C3, C9, CC | | |
| 63, 84-8B, 8D, 8F, D0-D3, FE, FF | yes | |
| 68 / 6A | | iz / ib |
| 69 / 6B | yes | iz / ib |
| 70-7F, EB (jcc, jmp rel8) | | ib |
| 80, 83, C0, C1, C6 / 81, C7 | yes | ib / iz |
| A8 / A9 | | ib / iz |
| B0-B7 / B8-BF | | ib / **iv**: 4, 2 with 66, 8 with REX.W |
| C2 | | iw (always 2) |
| E8, E9 (call, jmp rel32) | | always 4 |
| F6 / F7 | yes | ib / iz, **only if ModRM.reg is 0 or 1** (test) |
| 0F 05, 0F 0B, 0F A2 | | |
| 0F 10-17, 28-2F, 40-4F, 51-6F, 74-76, 7E, 7F, 90-9F, D1-FE | yes | |
| 0F 1F, AF, B6, B7, BE, BF, C1 | yes | |
| 0F 70-73, C2, C6 | yes | ib |
| 0F 80-8F (jcc rel32) | | always 4 |
| 0F 38 xx / 0F 3A xx | yes | — / ib |

**iz** is 4 bytes, or 2 with a 66 prefix, or 4 again with REX.W (REX.W beats 66).

Real decoders do exactly this, with tables. The CPU's own length decoder has another
problem: 66 changing an immediate from 4 to 2 bytes (a **length-changing prefix**)
stalls Intel's predecoder for several cycles.

## Gate

`ring_insn_length(code)` returns the length of the instruction at code, for 16 named
instructions and 80 random ones from the subset.
