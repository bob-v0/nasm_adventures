# Level 69 — SSE Scalar

*This is how x86-64 really does floating point: SSE, the same unit that does vectors,
used one number at a time.*

## Lesson: xmm registers

SSE has sixteen 128-bit registers, **xmm0-xmm15**. A scalar double lives in the low 64
bits; the `sd` ("scalar double") instructions use only those (`ss`: scalar single, a
float in the low 32 bits).

| instruction | effect |
|---|---|
| `movsd xmm0, [m]` / `movsd [m], xmm0` | load / store a double |
| `movq rax, xmm0` / `movq xmm0, rax` | move the 64 bits between register files, unchanged |
| `addsd`, `subsd`, `mulsd`, `divsd`, `sqrtsd` | arithmetic: `addsd xmm0, xmm1` (or `[m]`) |
| `minsd`, `maxsd` | |
| `cvtsi2sd xmm0, rax` | integer → double |
| `cvtsd2si rax, xmm0` | double → integer, **rounded as MXCSR says** |
| `cvttsd2si rax, xmm0` | double → integer, **truncated** (C's cast) |
| `andpd`, `xorpd`, `andnpd` | bitwise: clear or flip the sign bit with a mask |
| `pxor xmm0, xmm0` | 0.0 |

There are no immediates: constants live in memory (`dq 1000.0` in `.rodata`, which NASM
encodes for you).

The System V ABI passes doubles in xmm0-xmm7 and returns them in xmm0. **All xmm
registers are caller-saved**: a function may change any of them.

## Lesson: comparing

`ucomisd xmm0, xmm1` sets flags like an **unsigned** compare: CF for below, ZF for equal,
so use `jb`, `ja`, `jbe`, `jae`, `je`. And one more outcome integers don't have: if
either side is a NaN the result is **unordered**, and ZF = PF = CF = 1. `jp` catches it.
Every other test gives a surprising answer for a NaN (`je` is taken!), which is how
`x == x` becomes the classic NaN test.

## Lesson: MXCSR

**MXCSR** is SSE's control and status register (`stmxcsr [m]` / `ldmxcsr [m]`). Bits
13-14 are the **rounding mode** every SSE operation uses: 00 to nearest (ties to even,
the default), 01 down, 10 up, 11 toward zero. It belongs to the caller, like a global
setting: a library function rounds the way it's asked to, and doesn't change it.

## Gate

`ring_dtoa(x, buf)` prints a double with three decimals and returns the length. This is
a real library routine (C's `printf("%.3f")`), simplified: the rounding is the CPU's,
on the double product |x| × 1000.
