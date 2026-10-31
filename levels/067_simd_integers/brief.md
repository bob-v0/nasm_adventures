# Level 67 — SIMD Integers

*One instruction, sixteen pixels. The loop that took 4 000 cycles takes 400.*

## Lesson: SIMD

**SIMD** means "single instruction, multiple data". An xmm register holds 128 bits, and
the **packed** instructions treat them as several independent **lanes**, all computed
at once:

```
            byte 15                                   byte 0
xmm0   [ 200 | 17 | ... |  3 | 250 ]
xmm1   [  10 | 10 | ... | 10 |  10 ]
              paddb xmm0, xmm1      (16 additions, one instruction)
xmm0   [ 210 | 27 | ... | 13 |   4 ]    <- 250 + 10 wrapped to 4
```

The suffix says how wide the lanes are:

| suffix | lanes | example |
|---|---|---|
| `b` | 16 bytes | `paddb xmm0, xmm1`: 16 additions |
| `w` | 8 words | `paddw` |
| `d` | 4 dwords | `paddd`, `pmulld` |
| `q` | 2 qwords | `paddq` |

Each lane is computed on its own: a carry out of one byte doesn't reach the next.

Loading and storing: `movdqu xmm0, [m]` loads 16 bytes from any address. `movdqa` needs
a 16-byte **aligned** address (a multiple of 16) and faults otherwise; the game's CPU
checks, as real ones do. Arithmetic with a memory operand (`paddb xmm0, [m]`) needs
alignment too.

## Lesson: saturation

`paddb` wraps around: 250 + 10 = 4. For pixels, sound and many other signals you want
**saturation** instead: the result is clamped to the lane's range.

- `paddusb` (add, unsigned, saturating): 250 + 10 = 255;
- `paddsb` (signed): clamps to −128..127;
- `psubusb`: subtracts, and stops at 0.

No compare, no branch.

## Lesson: broadcasting

To add the same amount to every pixel, the amount has to be in every lane. That's a
**broadcast**. `movd xmm1, edx` puts 32 bits in the low lane (and zeros the rest). Then
spread byte 0 everywhere, either way:

- `pshufb xmm1, xmm2` with xmm2 all zero (SSSE3): a byte shuffle in which every lane
  takes byte 0;
- or `punpcklbw xmm1, xmm1` (byte 0 → word 0), `pshuflw xmm1, xmm1, 0` (word 0 → the 4
  low words), `pshufd xmm1, xmm1, 0` (dword 0 → all four).

Level 66 is all about shuffles.

## Lesson: the tail

n isn't always a multiple of 16. The usual shape is a vector loop for the n / 16 full
blocks, then a scalar loop for the last n % 16 pixels. Don't write a whole vector over
the end: it would change bytes that aren't yours (the tests check the bytes after the
image).

## Gate

`ring_brighten(pixels, n, amount)` adds amount (0..255) to each of the n grey pixels
(bytes), clamping at 255. Nothing after pixel n − 1 may change.

Budget: **0.4 cycles per pixel**, plus a small fixed allowance.
