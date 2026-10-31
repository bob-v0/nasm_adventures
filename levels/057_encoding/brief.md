# Level 57 — Encoding I

*Arc X: under the mnemonics. NASM has turned your text into bytes for 127 levels. Now
you do it.*

## Lesson: the shape of an instruction

Every x86-64 instruction is built from the same parts, always in this order:

```
[prefixes] [REX] opcode [ModRM] [SIB] [displacement] [immediate]
                 1-3     0-1     0-1   0, 1, 2 or 4   0, 1, 2, 4 (8)   bytes
```

Only the **opcode** (the byte or bytes that say which instruction it is) is always
there. The opcode decides which of the other parts follow. This level uses no prefixes
and no REX (that's level 56), and only 32-bit registers.

![The parts of an instruction, and mov [rsp-8], eax taken apart](format.svg)

## Lesson: register numbers

Inside an instruction, registers are 3-bit numbers:

| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| eax / al | ecx / cl | edx / dl | ebx / bl | esp / ah | ebp / ch | esi / dh | edi / bh |

Some opcodes have the register built in. `B8+r id` is mov r32, imm32: `mov ecx, imm` is
B9 (B8 + 1) followed by the 4 immediate bytes, little-endian.

## Lesson: ModRM

Most two-operand instructions have one register operand and one that is a register
**or memory** ("r/m"). The **ModRM** byte, right after the opcode, says which:

```
  7 6 | 5 4 3 | 2 1 0
  mod |  reg  |  r/m
```

- **mod = 3**: r/m is a register too.
- **mod = 0**: memory at [r/m]; **mod = 1**: [r/m + disp8]; **mod = 2**: [r/m + disp32].
- Two special cases: r/m = 4 (esp's number) means **a SIB byte follows**, and mod = 0
  with r/m = 5 means [rip + disp32].

Example: `add eax, ecx` is opcode 01 with mod = 3, reg = ecx (1), r/m = eax (0):
11 001 000 = **0xC8**, so the bytes are `01 C8`.

The opcode says which side is the destination: `01 /r` is add r/m32, r32 (the result
goes into r/m), `03 /r` is add r32, r/m32 (into reg). `89`/`8B` are the same pair for
mov.

**Opcode extensions.** Some opcodes take one operand plus an immediate. They have no
second register, so they use the reg field as 3 more opcode bits, written `/digit`:

- `83 /5 ib` = sub r/m32, imm8 (sign extended); `83 /0` add; `83 /7` cmp;
- `C1 /4 ib` shl; `F7 /3` neg; `F7 /2` not;
- `FF /0` inc; `FF /1` dec; `C6 /0 ib` mov r/m8, imm8.

## Lesson: SIB

When an address has an index register, or its base is esp/rsp, a **SIB** byte
("scale, index, base") follows ModRM:

```
  7 6   | 5 4 3 | 2 1 0
  scale | index | base        address = base + index × 2^scale + disp
```

Index 4 means "no index". That's how `[rsp]` is spelled: ModRM r/m = 4, then SIB 0x24.

## Lesson: immediates, displacements, jumps

Displacements and immediates come last, little-endian. Many opcodes have a short form
with an 8-bit sign-extended immediate (`83`) and a long one (`81`); assemblers pick the
short one when the value fits.

Jumps are **relative to the end of the jump instruction**: `75 FA` (jnz rel8 −6) goes
back 6 bytes from the byte after itself. `EB` is jmp rel8, `7x` jcc rel8, and `E9` /
`0F 8x` are the rel32 forms.

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

Write the 23 instructions in the starter as `db` lines only (labels are allowed). The
game decodes your bytes and compares them with the 23 instructions (any valid encoding
counts), then runs them and checks the registers.
