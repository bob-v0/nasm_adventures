# Level 66 — Shuffles

*Arithmetic stays in its lane. Everything else (reversing, interleaving, transposing,
looking things up) is a **shuffle**: moving data between lanes.*

## Lesson: pshufb

`pshufb xmm0, xmm1` (SSSE3) is the most general byte shuffle. For each of the 16 result
bytes, the **control** byte at the same position in xmm1 says where to get it:

- its low 4 bits pick which byte of the old xmm0 to copy;
- if its top bit is set (0x80), the result byte is 0 instead.

![pshufb: each control byte picks the source of one result byte](pshufb.svg)

Three useful controls, written byte 0 first (memory order, the order you'd write them
after `db`):

```
control:   15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
result:    the 16 bytes reversed

control:    3  2  1  0  7  6  5  4 11 10  9  8 15 14 13 12
result:    each dword byte-swapped (four bswaps: network order)

control:    0  0  0 ... 0
result:    byte 0 everywhere (a broadcast, level 67)
```

The control is just data. Build it once in `.rodata` (`align 16`, then `db ...`) and
keep it in a register for the whole loop.

pshufb is also a 16-entry table lookup: put the table in xmm0 and the indexes in the
control. The boss level will need that.

## Lesson: the other shuffles

| instruction | what it does |
|---|---|
| `pshufd xmm0, xmm1, imm8` | dword i of the result = dword (imm >> 2i) & 3 of xmm1. `0x1B` reverses the four dwords, `0` broadcasts dword 0 |
| `pshuflw` / `pshufhw` | the same for the 4 low / 4 high words |
| `punpcklbw xmm0, xmm1` | interleave the low 8 bytes: a0 b0 a1 b1 ... (`punpckh*`: the high halves; also `wd`, `dq`, `qdq`). With a zero register: zero-extend bytes to words |
| `palignr xmm0, xmm1, k` | the 16 bytes starting at byte k of the 32-byte pair xmm0:xmm1: a window that slides across two registers |
| `psrldq` / `pslldq xmm0, k` | shift the whole register by k **bytes** |
| `shufps` | two dwords from each of two registers |

Example: transposing a 4×4 matrix of dwords is two rounds of shuffles,
`punpckldq`/`punpckhdq` then `punpcklqdq`/`punpckhqdq`: eight instructions for sixteen
numbers.

## Gate

`ring_reverse(buf, n)` reverses the n bytes at buf in place, without touching anything
after byte n − 1.

Budget: **0.3 cycles per byte**, plus a small fixed allowance.
