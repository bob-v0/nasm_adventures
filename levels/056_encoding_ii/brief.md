# Level 56 — Encoding II

*Level 57's instructions are the 1985 subset. Everything since (64-bit registers, eight
more of them, SSE, AVX) was squeezed in with prefixes.*

## Lesson: REX

Level 57's register fields are 3 bits: room for 8 registers. To reach r8–r15 and 64-bit
operands, 64-bit mode reuses the bytes 0x40–0x4F as the **REX** prefix:

```
  0 1 0 0 | W | R | X | B
```

- **W**: 64-bit operand size. Without it most instructions are 32-bit. (Writing a 32-bit
  register zeroes the upper half, which is why 32 bits is the default.)
- **R**, **X**, **B**: a 4th, top bit for ModRM.reg, SIB.index and ModRM.r/m
  respectively. B also extends SIB.base, and the register built into opcodes like
  `B8+r`. That's how registers 8–15 are named.
- Any REX turns ah, ch, dh, bh into **spl, bpl, sil, dil**: `mov dil, 7` needs an empty
  REX (0x40).

Example: `mov r9, rax` is 89 /r with r/m = r9 (1, plus B) and reg = rax (0). REX = 0100
1 0 0 1 = 0x49, ModRM = 11 000 001 = 0xC1: `49 89 C1`.

`mov rax, imm64` (REX.W B8) is the only instruction with an 8-byte immediate.

Two quirks carry over from level 57's special cases, because REX.B doesn't change them:

- r/m = 4 means "SIB follows", so **r12** (100 + B) as a base needs a SIB byte too;
- mod = 0, r/m = 5 means rip-relative, so **r13** (101 + B) as a base needs mod = 1 with
  a zero displacement.

## Lesson: legacy prefixes

| prefix | meaning |
|---|---|
| `66` | 16-bit operand size (`mov ax, imm16`) |
| `67` | 32-bit addresses |
| `F0` | lock |
| `F3` / `F2` | rep / repne for string instructions |
| `2E` `3E` `26` `64` `65` `36` | segments (fs and gs still matter) |

Order: legacy prefixes first, then REX **immediately** before the opcode.

## Lesson: SSE encodings

SSE reused those prefixes as part of the opcode. They're called **mandatory prefixes**:

| bytes | instruction |
|---|---|
| `0F 58` | addps |
| `66 0F 58` | addpd |
| `F3 0F 58` | addss |
| `F2 0F 58` | addsd |

Packed integer instructions are `66 0F xx`; `F3 0F 6F` is movdqu. REX still goes right
before the `0F`, after the mandatory prefix.

## Lesson: VEX

AVX needed a third operand and 256-bit lengths, and there was no room left. So **VEX**
packs REX, the mandatory prefix and the new fields into 2 or 3 bytes:

```
C5 | R̄ v̄v̄v̄v̄ L pp |                        2-byte form (map 0F, no X/B/W)
C4 | R̄ X̄ B̄ mmmmm  | W v̄v̄v̄v̄ L pp |        3-byte form
```

- R̄, X̄, B̄ and vvvv are stored **inverted** (vvvv = 1111 means "no register").
- vvvv is the extra source register; L = 1 for 256 bits.
- pp is the old mandatory prefix: 0 none, 1 = 66, 2 = F3, 3 = F2.
- mmmmm is the opcode map: 1 = 0F, 2 = 0F 38, 3 = 0F 3A.

Worked example: `vpaddd ymm2, ymm0, ymm0` (66 0F FE in SSE form):

```
C5                    2-byte VEX
1 1111 1 01 = FD      R̄ = 1 (R = 0), vvvv = ~0000 (ymm0), L = 1, pp = 01 (66)
FE                    the opcode
D0                    ModRM: 11 010 000 (reg = ymm2, r/m = ymm0)
```

(In 32-bit mode C4 and C5 were LES and LDS; inverting the bits made VEX impossible to
confuse with them.) EVEX, AVX-512's prefix, is the same idea in 4 bytes starting with
62.

## Gate

Write the 26 instructions in the starter as `db` lines only (labels are allowed). The
game decodes your bytes and compares them with the 26 instructions (any valid encoding
counts), then runs them and checks the registers.
