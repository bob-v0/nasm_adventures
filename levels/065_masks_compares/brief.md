# Level 65 — Masks & Compares

*SIMD loops can't branch per lane. So compares don't set flags: they produce data, a
**mask**, and the program asks questions about the whole mask at once.*

## Lesson: compares make masks

`pcmpeqb xmm0, xmm1` compares 16 pairs of bytes. In each lane where they're equal it
writes **0xFF**; where they aren't, **0x00**. (`pcmpeqw`/`d`/`q` do wider lanes;
`pcmpgtb` and friends do signed greater-than.)

The result is an ordinary vector, a **mask**. You can:

- `pand` it with data to keep only the matching lanes (`pandn` for the others);
- add it: 0xFF is −1, so subtracting masks counts matches;
- or ask a question about it:

| instruction | answer |
|---|---|
| `pmovmskb eax, xmm0` | the top bit of each byte, packed into the low 16 bits of eax |
| `ptest xmm0, xmm0` | ZF = 1 if xmm0 is all zeros (no trip through a general register) |
| `movmskps` / `movmskpd` | the sign bits of 4 floats / 2 doubles |

![Compare, mask, movemask: finding 'o' in 16 bytes](movemask.svg)

## Lesson: from mask to position

With the mask in eax, bit i set means lane i matched. Example: searching
`hello, world` for `o` gives eax = 0x0110 (bits 4 and 8).

| question | instruction |
|---|---|
| the **first** match | the lowest set bit: `tzcnt eax, eax` counts trailing zeros (`bsf` is the old version, undefined for 0) |
| the **last** match | `lzcnt` (then 31 − it) or `bsr` |
| how many matches | `popcnt` |
| the next match | clear the lowest set bit: `blsr eax, eax` (or `lea ecx, [rax − 1]` / `and eax, ecx`) |

This is how every fast `strlen`, `memchr`, `strchr` and JSON parser works: one compare,
one movemask, one test-and-branch per 16 (or 32, or 64) bytes.

## Gate

`ring_memchr(buf, byte, n)` returns the index of the first occurrence of byte (0..255)
among the n bytes at buf, or −1 if there's none. Bytes after the n-th don't count, even
if they match (the tests put matches there).

Budget: **0.3 cycles per byte searched** (up to the match, or all n), plus a small fixed
allowance.
