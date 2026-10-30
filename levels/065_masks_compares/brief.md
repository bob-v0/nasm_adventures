# Level 65 — Masks & Compares

*SIMD loops can't branch per lane. So compares don't set flags: they produce data, a
**mask**, and the program asks questions about the whole mask at once.*

## Lesson: compares make masks

`pcmpeqb xmm0, xmm1` compares 16 pairs of bytes and writes **0xFF** in each lane where
they're equal, **0x00** where they aren't. (`pcmpeqw`/`d`/`q` for wider lanes,
`pcmpgtb` & co. for signed greater-than.) The result is a normal vector: you can `pand`
it with data to keep only some lanes, `pandn` it, add it (0xFF is −1: subtracting masks
counts matches), or ask questions:

| instruction | answer |
|---|---|
| `pmovmskb eax, xmm0` | the top bit of each byte, packed into 16 bits of eax |
| `ptest xmm0, xmm0` | ZF = 1 if xmm0 is all zeros (no flags needed from a GPR) |
| `movmskps` / `movmskpd` | the sign bits of 4 floats / 2 doubles |

## Lesson: from mask to position

With the mask in eax, bit i set means lane i matched. The **first** match is the lowest
set bit: `tzcnt eax, eax` counts trailing zeros (`bsf` is the old version, undefined for
0). The last match: `lzcnt` (31 − it) or `bsr`. The number of matches: `popcnt`. Clearing
the lowest set bit to get the next one: `blsr eax, eax` (or `lea ecx, [rax − 1]` /
`and eax, ecx`).

This is how every fast `strlen`, `memchr`, `strchr` and JSON parser works: one compare,
one movemask, one test-and-branch per 16 (or 32, 64) bytes.

## Gate

`ring_memchr(buf, byte, n)` returns the first index or −1, within **0.3 cycles per byte
searched**.
