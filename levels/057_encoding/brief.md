# Level 57 — Encoding I

*Arc X: under the mnemonics. NASM has turned your text into bytes for 127 levels. Now
you do it.*

## Lesson: the shape of an instruction

```
[prefixes] [REX] opcode [ModRM] [SIB] [displacement] [immediate]
              (56)  1-3      0-1     0-1   0, 1, 2 or 4   0, 1, 2, 4 (8)
```

Only the opcode is always there. Everything else depends on it. This level: no prefixes,
no REX (that's level 56), 32-bit registers.

## Lesson: register numbers

| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| eax / al | ecx / cl | edx / dl | ebx / bl | esp / ah | ebp / ch | esi / dh | edi / bh |

Some opcodes contain the register: `B8+r id` is mov r32, imm32, so `mov ecx, imm` is B9
followed by 4 bytes, little-endian.

## Lesson: ModRM

For opcodes with two operands, one is a register and the other is a register **or
memory** ("r/m"). The ModRM byte says which:

```
  7 6 | 5 4 3 | 2 1 0
  mod |  reg  |  r/m
```

- **mod = 3**: r/m is a register too.
- **mod = 0**: memory at [r/m], **mod = 1**: [r/m + disp8], **mod = 2**: [r/m + disp32].
- r/m = 4 (esp's number) means **a SIB byte follows**; mod = 0 with r/m = 5 means
  [rip + disp32].

The opcode says which side is the destination: `01 /r` is add r/m32, r32 (into r/m),
`03 /r` is add r32, r/m32 (into reg). `89`/`8B` the same for mov.

**Opcode extensions:** some opcodes have only one operand plus an immediate, and use the
reg field as 3 more opcode bits, written `/digit`: `83 /5 ib` = sub r/m32, imm8 (sign
extended), `83 /0` add, `83 /7` cmp. `C1 /4 ib` shl, `F7 /3` neg, `F7 /2` not,
`FF /0` inc, `FF /1` dec, `C6 /0 ib` mov r/m8, imm8.

## Lesson: SIB

```
  7 6   | 5 4 3 | 2 1 0
  scale | index | base        address = base + index × 2^scale + disp
```

Index 4 means "no index", which is how `[rsp]` is spelled: ModRM r/m = 4, SIB 0x24.

## Lesson: immediates, displacements, jumps

Little-endian, after everything else. Many opcodes have a short form with an 8-bit
sign-extended immediate (`83`) and a long one (`81`): assemblers pick the short one.

Jumps are **relative to the end of the jump**: `75 FA` (jnz rel8 −6) goes back 6 bytes
from the byte after itself. `EB` jmp rel8, `7x` jcc rel8, `E9`/`0F 8x` rel32.

## A few opcodes

| opcode | instruction |
|---|---|
| `01 /r`, `29 /r`, `31 /r`, `39 /r`, `85 /r` | add, sub, xor, cmp, test r/m32, r32 |
| `89 /r`, `8B /r`, `8D /r` | mov r/m32, r32; mov r32, r/m32; lea r32, m |
| `24 ib` | and al, imm8 |
| `6B /r ib` | imul r32, r/m32, imm8 |
| `0F B6 /r` | movzx r32, r/m8 |
| `0F 94 /0` | sete r/m8 (the reg field is ignored: use 0) |

The whole map is in the Intel SDM, volume 2, appendix A, and on sandpile.org.

## Gate

The 23 instructions in the starter, as `db` lines only. The game decodes your bytes
(any valid encoding counts) and runs them.
