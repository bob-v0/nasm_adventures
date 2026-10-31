# Level 56 — Encoding II

*Level 57's instructions are the 1985 subset. Everything since (64-bit registers, eight
more of them, SSE, AVX) was squeezed in with prefixes.*

## Lesson: REX

In 64-bit mode the bytes 0x40-0x4F are the **REX** prefix:

```
  0 1 0 0 | W | R | X | B
```

- **W**: 64-bit operand size. Without it most instructions are 32-bit (writing a 32-bit
  register zeroes the upper half, which is why that's the default).
- **R**, **X**, **B**: a 4th bit for ModRM.reg, SIB.index and ModRM.r/m (or SIB.base, or
  the register in `B8+r`): registers 8-15.
- Any REX turns ah, ch, dh, bh into **spl, bpl, sil, dil**: `mov dil, 7` needs an empty
  REX (0x40).

`mov rax, imm64` (REX.W B8) is the only instruction with an 8-byte immediate.

Two quirks inherited from level 57's table: r/m = 4 means SIB, so **r12** as a base needs
one too; mod = 0, r/m = 5 means rip-relative, so **r13** as a base needs mod = 1 with a
zero displacement.

## Lesson: legacy prefixes

| prefix | meaning |
|---|---|
| `66` | 16-bit operand size (`mov ax, imm16`) |
| `67` | 32-bit addresses |
| `F0` | lock |
| `F3` / `F2` | rep / repne for string instructions |
| `2E` `3E` `26` `64` `65` `36` | segments (fs and gs still matter) |

Order: legacy prefixes, then REX **immediately** before the opcode.

## Lesson: SSE encodings

SSE reused the prefixes as part of the opcode (**mandatory prefixes**): `0F 58` is
addps, `66 0F 58` addpd, `F3 0F 58` addss, `F2 0F 58` addsd. Packed integer instructions
are `66 0F xx`; `F3 0F 6F` is movdqu. REX still goes right before the `0F`.

## Lesson: VEX

AVX needed a third operand and 256-bit lengths, and there was no room left, so **VEX**
packs REX, the mandatory prefix and the new fields into 2 or 3 bytes:

```
C5  | R̄ v̄v̄v̄v̄ L pp |                       2-byte form (map 0F, no X/B/W)
C4  | R̄ X̄ B̄ mmmmm  | W v̄v̄v̄v̄ L pp |       3-byte form
```

R̄, X̄, B̄ and vvvv are stored **inverted** (vvvv = 1111 means "no register"), L = 1 for
256 bits, pp encodes the old mandatory prefix (0 none, 1 = 66, 2 = F3, 3 = F2), mmmmm the
opcode map (1 = 0F, 2 = 0F 38, 3 = 0F 3A). `vpaddd ymm2, ymm0, ymm0` is C5, then
R̄ = 1, vvvv = ~0 = 1111, L = 1, pp = 01: 1 1111 1 01 = 0xFD, then FE, then ModRM.
(In 32-bit mode C4 and C5 were LES and LDS; inverting the bits made VEX impossible to
confuse with them.) EVEX, AVX-512's prefix, is the same idea in 4 bytes starting with 62.

## Gate

The 26 instructions in the starter as `db` lines.
