# Level 161 — Shifts & Rotates

*Moving bits sideways: the cheapest multiplication there is.*

## Lesson: shifts

In decimal, appending a zero multiplies by 10: 42 becomes 420. In binary, moving
every bit one place left multiplies by 2, and moving right divides by 2. That is a
**shift**:

```
shl rax, 3     ; shift left 3: multiply by 8 (bits fall off the top into CF)
shr rax, 3     ; shift right, filling with 0s: unsigned divide by 8
sar rax, 3     ; shift right, filling with copies of the sign bit: signed divide by 8
               ;   (rounding toward -infinity, unlike idiv!)
rol rax, 8     ; rotate: bits that fall off one end come back at the other
ror rax, 8
```

For example, `shl` by 3 turns `0000_0101` (5) into `0010_1000` (40).

A variable count must be in **`cl`** (`shl rax, cl`), and the CPU uses only its low 6
bits (5 for 32-bit operands): a shift by 64 is a shift by 0, **not** a result of 0.

`shld dst, src, cl` shifts `dst` left and fills the vacated bits from the top of
`src`, a shift across two registers. `shrd` does the same to the right. Together with
a `shl` they shift 128-bit numbers.

## Lesson: packing fields

Small values are often packed side by side into one integer. **RGB565** stores a
colour in 16 bits: 5 bits of red, 6 of green, 5 of blue:

```
bit   15     11 10        5 4      0
      [ r r r r r | g g g g g g | b b b b b ]
```

![Each 8-bit channel keeps only its top bits (5, 6, 5); then they are moved into place and combined](rgb565.svg)

To build it from 8-bit channels: drop the low bits that won't fit (`r >> 3`,
`g >> 2`, `b >> 3`), move each part into its place (`<< 11`, `<< 5`) and `or` them
together.

## Gate

| Inputs | Output |
|---|---|
| `rdi` = r, `rsi` = g, `rdx` = b (each 0–255) | `rax` = the RGB565 value |
| `r11` : `r10` = a 128-bit value (high : low), `rcx` = n (0–127) | `r9` : `r8` = the value shifted left by n (mod 2¹²⁸) |

`rdi`, `rsi`, `rdx`, `r10` and `r11` must be unchanged. Constraints: at most 26
instructions; must use `shl`, `shr` and `shld`; no multiplication or division.
