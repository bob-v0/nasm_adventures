# Level 54 — Disassembler

*objdump, gdb's `x/i`, every debugger and every crash report turn bytes back into text.
You have level 55's decoder; now print what it found.*

## The job

Read machine code from stdin (at most 64 KiB) and print it as NASM source, one line per
instruction. The code sits at address 0: the first byte is offset 0x0. The game compares
your output character by character, so the format below is exact.

## The subset

| bytes | instruction |
|---|---|
| `01 03 09 0B 21 23 29 2B 31 33 39 3B /r` | add, or, and, sub, xor, cmp (r/m, reg or reg, r/m) |
| `89 /r`, `8B /r`, `85 /r`, `8D /r` | mov r/m, reg; mov reg, r/m; test r/m, reg; lea reg, m |
| `83 /n ib`, `81 /n id` | add (0), or (1), and (4), sub (5), xor (6), cmp (7) r/m, imm |
| `C7 /0 id` | mov r/m, imm32 |
| `FF /0`, `FF /1` | inc, dec r/m |
| `B8+r id` (`io` with REX.W) | mov reg, imm32 (imm64) |
| `50+r`, `58+r` | push, pop (always 64-bit) |
| `70+cc cb`, `0F 80+cc cd` | jcc rel8, rel32 |
| `EB cb`, `E9 cd`, `E8 cd` | jmp rel8, jmp rel32, call rel32 |
| `C3`, `90`, `0F 05` | ret, nop, syscall |

Any of them may have a REX before the opcode. REX.W selects 64-bit registers (rax ...
r15); without it they're 32-bit (eax ... r15d). The condition codes 0–F are, in order:
`jo jno jb jae je jne jbe ja js jns jp jnp jl jge jle jg`.

## The format

- Lowercase: the mnemonic, one space, then the operands separated by `, `. No trailing
  spaces.
- Numbers in hex: `0x` and the digits, lowercase, no leading zeros (`0x0` for zero).
  Negative values: `-0x` and the magnitude.
- **Immediates** are signed, sign-extended from their size (`83 C0 FF` is
  `add eax, -0x1`). The one exception is `B8+r`, which is unsigned.
- **Memory**: `[`, the base register, then `+index` and `*scale` (omitted when the scale
  is 1), then `+0x..` or `-0x..` for a non-zero displacement, then `]`. Registers inside
  brackets always have their 64-bit names. With no base and no index, just the signed
  displacement: `[0x1000]`. Examples: `[rax]`, `[rbp-0x8]`, `[rbx+rcx*8+0x10]`,
  `[r12*4-0x20]`.
- **rip-relative** (mod = 0, r/m = 5): `[rel 0x..]` with the **target address**, which
  is the address of the next instruction plus the displacement.
- A **size keyword**, `qword ` or `dword ` before the `[`, only when no register operand
  gives the size: the `83`/`81`/`C7` forms, and inc/dec, with a memory operand.
- **Branches**: the target address: `jne 0x2a`, `call 0x0`.

```
48 8b 47 08          mov rax, [rdi+0x8]
4c 8d 54 0d f0       lea r10, [rbp+rcx-0x10]
48 c7 00 00 00 00 80 mov qword [rax], -0x80000000
75 f9                jne 0x2           (at offset 7: 9 − 7)
48 8b 05 10 00 00 00 mov rax, [rel 0x17]
```

## Lesson: decode, then print

A rip-relative operand and a branch target both depend on where the instruction
**ends**. And the immediate comes after the displacement in the bytes, but you print
the memory operand first. So read the whole instruction into variables (or remember
where its pieces are), and only then print.

Tables of strings make the printing short: `dq name0, name1, ...`, each pointing at a
NUL-terminated name.

## Gate

Six named inputs and six random programs of 10 to 40 instructions: the output must
match exactly, and the program must exit with status 0.
