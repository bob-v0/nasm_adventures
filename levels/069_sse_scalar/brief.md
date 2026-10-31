# Level 69 — SSE Scalar

*This is how x86-64 really does floating point: SSE, the same unit that does vectors,
used one number at a time.*

## Lesson: xmm registers

SSE gives you sixteen 128-bit registers, **xmm0–xmm15**. A **scalar** double (a single
number, not a vector) lives in the low 64 bits. The `sd` instructions ("scalar double")
use only those bits; the `ss` ones ("scalar single") use a float in the low 32.

| instruction | effect |
|---|---|
| `movsd xmm0, [m]` / `movsd [m], xmm0` | load / store a double |
| `movq rax, xmm0` / `movq xmm0, rax` | copy the 64 bits between register files, unchanged |
| `addsd`, `subsd`, `mulsd`, `divsd`, `sqrtsd` | arithmetic: `addsd xmm0, xmm1` (or `[m]`) |
| `minsd`, `maxsd` | minimum, maximum |
| `cvtsi2sd xmm0, rax` | integer → double |
| `cvtsd2si rax, xmm0` | double → integer, **rounded as MXCSR says** |
| `cvttsd2si rax, xmm0` | double → integer, **truncated** (like C's cast) |
| `andpd`, `xorpd`, `andnpd` | bitwise: clear or flip the sign bit with a mask |
| `pxor xmm0, xmm0` | 0.0 |

There are no floating-point immediates. Constants live in memory: `dq 1000.0` in
`.rodata`, which NASM encodes for you.

The System V ABI passes doubles in xmm0–xmm7 and returns them in xmm0. **All xmm
registers are caller-saved**: a function may change any of them.

## Lesson: comparing

`ucomisd xmm0, xmm1` sets the flags as if it were an **unsigned** integer compare. So you
branch with the unsigned jumps: `jb`, `ja`, `jbe`, `jae`, `je`.

Floats have one outcome integers don't: if either side is a NaN, the result is
**unordered**.

| outcome | ZF | PF | CF |
|---|---|---|---|
| xmm0 > xmm1 | 0 | 0 | 0 |
| xmm0 < xmm1 | 0 | 0 | 1 |
| equal | 1 | 0 | 0 |
| unordered (a NaN) | 1 | 1 | 1 |

Only `jp` tells unordered apart. Every other jump gives a surprising answer for a NaN
(`je` is taken!). Comparing x with itself is the classic NaN test: only a NaN is
unordered with itself.

## Lesson: MXCSR

**MXCSR** is SSE's control and status register (`stmxcsr [m]` / `ldmxcsr [m]`). Bits
13–14 are the **rounding mode** every SSE operation uses: 00 to nearest (ties to even,
the default), 01 down, 10 up, 11 toward zero.

MXCSR belongs to the caller, like a global setting. A library function rounds the way
it's asked to, and doesn't change it.

## Gate

`ring_dtoa(x, buf)` writes x as text with three decimals into buf and returns the
length in rax. It's a real library routine (C's `printf("%.3f")`), simplified:

- `3.25` → `3.250`, `-12.5` → `-12.500`, `0.1` → `0.100`;
- a `-` whenever the sign bit is set, so −0.0 → `-0.000`;
- NaN → `nan`, ±infinity → `inf` / `-inf`;
- otherwise n = |x| × 1000 (a double product), rounded to an integer the way MXCSR's
  rounding mode says, printed as n / 1000, `.`, and n % 1000 in exactly three digits.

Some tests run with a rounding mode other than the default. MXCSR must be unchanged
when you return.
