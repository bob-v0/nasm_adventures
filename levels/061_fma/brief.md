# Level 61 — FMA

*Every math library's `exp`, `sin` and `log` is the same three ideas: shrink the input
to a small range, evaluate a polynomial there, scale back. FMA makes the polynomial fast
and the shrinking exact.*

## Lesson: fused multiply-add

`vfmadd231ps ymm0, ymm1, ymm2` computes ymm0 = ymm1 · ymm2 + ymm0 with **one rounding**:
the product is never rounded on its own. Faster (one instruction, 4 cycles) and more
accurate than `vmulps` + `vaddps`. The digits name which operands multiply:

| form | computes (operands 1, 2, 3) |
|---|---|
| `vfmadd132ps a, b, c` | a = a·c + b |
| `vfmadd213ps a, b, c` | a = b·a + c |
| `vfmadd231ps a, b, c` | a = b·c + a |

`vfmsub` subtracts the addend, `vfnmadd` negates the product (−b·c + a), `ss`/`sd` are the
scalar forms. FMA is its own cpuid feature (leaf 1, ecx bit 12); this level's CPU has it.

## Lesson: Horner's rule

A polynomial c₀ + c₁r + c₂r² + ... + c₇r⁷ is evaluated inside out:
((c₇·r + c₆)·r + c₅)·r + ... + c₀: seven multiply-adds, one FMA each.

## Lesson: range reduction

e^x for x up to 88 is enormous; a polynomial can't follow it. But
e^x = 2^k · e^r with k = round(x / ln 2) and r = x − k·ln 2, and |r| ≤ ln 2 / 2 ≈ 0.35,
where the Taylor series of e^r up to r⁷/7! is accurate to about 10⁻⁹.

The subtraction r = x − k·ln 2 is cancellation again (level 68): x and k·ln 2 are nearly
equal. The classic trick: split ln 2 into ln2hi (few bits, so k·ln2hi is exact) and the
small rest ln2lo, and subtract in two steps. With FMA each step rounds only once.

2^k needs no arithmetic at all: a float is 1.f × 2^(e − 127) with e in bits 23-30, so
adding k << 23 to the bits of p (an integer add, `vpaddd`) multiplies p by 2^k.

## Lesson: ULPs

Floating-point error is measured in **ULPs**, units in the last place: how many
representable floats lie between the result and the true value. A correctly rounded
result is 0 ULPs away; good libraries promise 1 or 2. For two positive floats, the
difference of their bit patterns as integers *is* their distance in ULPs.

## Lesson: masked tails

For the last n % 8 elements, `vmaskmovps ymm0, ymm_mask, [m]` loads only the lanes whose
mask element has its top bit set (the others read as 0, and can't fault), and
`vmaskmovps [m], ymm_mask, ymm0` stores only those lanes. One more pass of the same
code, no scalar version needed.

## Gate

`ring_exp(in, out, n)`: within **2 ULPs**, under **1 cycle per element**, with FMA.
