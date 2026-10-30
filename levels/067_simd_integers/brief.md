# Level 67 — SIMD Integers

*One instruction, sixteen pixels. The loop that took 4 000 cycles takes 400.*

## Lesson: SIMD

**SIMD**, single instruction, multiple data: an xmm register holds 128 bits, and the
packed instructions treat them as several independent **lanes**:

| suffix | lanes | example |
|---|---|---|
| `b` | 16 bytes | `paddb xmm0, xmm1`: 16 additions |
| `w` | 8 words | `paddw` |
| `d` | 4 dwords | `paddd`, `pmulld` |
| `q` | 2 qwords | `paddq` |

Each lane is computed on its own: a carry out of one byte doesn't reach the next.
`movdqu xmm0, [m]` loads 16 bytes from anywhere; `movdqa` needs a 16-byte aligned
address and faults otherwise (the game's CPU checks, as real ones do), and the
arithmetic instructions with a memory operand (`paddb xmm0, [m]`) need alignment too.

## Lesson: saturation

`paddb` wraps: 250 + 10 = 4. For pixels, sound and many other signals you want
**saturation**: the result is clamped to the range. `paddusb` (unsigned saturate) gives
255; `paddsb` clamps to −128..127; `psubusb` stops at 0. No compare, no branch.

## Lesson: broadcasting

To add the same amount to every pixel, it has to be in every lane. `movd xmm1, edx`
puts 32 bits in the low lane (and zeros the rest). Then spread it:
- `pshufb xmm1, xmm2` with xmm2 all zero (SSSE3): byte shuffle, every lane takes byte 0;
- or `punpcklbw xmm1, xmm1` (bytes → words), `pshuflw xmm1, xmm1, 0` (word 0 → 4 low
  words), `pshufd xmm1, xmm1, 0` (dword 0 → all four).

Level 66 is all about shuffles.

## Lesson: the tail

n isn't always a multiple of 16. The usual shape: a vector loop for n / 16 blocks, then a
scalar loop for the last n % 16. Writing a whole vector over the end would change bytes
that aren't yours (the game checks the bytes after the image).

## Gate

`ring_brighten(pixels, n, amount)` within **0.4 cycles per pixel** (plus a little).
