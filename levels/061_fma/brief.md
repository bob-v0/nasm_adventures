# Level 61 — FMA

*Every math library's `exp`, `sin` and `log` is the same three ideas: shrink the input
to a small range, evaluate a polynomial there, scale back. FMA makes the polynomial fast
and the shrinking exact.*

## Lesson: fused multiply-add

`vfmadd231ps ymm0, ymm1, ymm2` computes ymm0 = ymm1 · ymm2 + ymm0 with **one rounding**:
the product is never rounded on its own. That's both faster than `vmulps` + `vaddps`
(one instruction, 4 cycles) and more accurate.

The three digits say which operands play which role. Read them as "multiply operand
*first digit* by operand *second digit*, add operand *third digit*", and the result
always goes into operand 1:

| form | computes (operands 1, 2, 3 = a, b, c) |
|---|---|
| `vfmadd132ps a, b, c` | a = a·c + b |
| `vfmadd213ps a, b, c` | a = b·a + c |
| `vfmadd231ps a, b, c` | a = b·c + a |

Variants: `vfmsub` subtracts the addend, `vfnmadd` negates the product (−b·c + a), and
`ss`/`sd` are the scalar forms. FMA is its own cpuid feature (leaf 1, ecx bit 12); this
level's CPU has it.

## Lesson: Horner's rule

A polynomial c₀ + c₁r + c₂r² + ... + c₇r⁷ is cheapest evaluated inside out:

    ((c₇·r + c₆)·r + c₅)·r + ... + c₀

Seven multiply-adds, one FMA each.

## Lesson: range reduction

e^x for x up to 88 is enormous; no short polynomial can follow it. So shrink the input
first:

    e^x = 2^k · e^r,   with k = round(x / ln 2) and r = x − k·ln 2

Now |r| ≤ ln 2 / 2 ≈ 0.35, and there the Taylor series of e^r up to r⁷/7! is accurate to
about 10⁻⁹.

One trap: r = x − k·ln 2 is cancellation again (level 68), since x and k·ln 2 are nearly
equal. The classic trick splits ln 2 into ln2hi (few significant bits, so k·ln2hi is
exact) plus the small rest ln2lo, and subtracts in two steps. With FMA each step rounds
only once.

Scaling by 2^k needs no arithmetic at all. A float is 1.f × 2^(e − 127) with e in bits
23–30, so adding k << 23 to the bits of p (an integer add, `vpaddd`) multiplies p by
2^k.

## Lesson: ULPs

Floating-point error is measured in **ULPs**, "units in the last place": how many
representable floats lie between the result and the true value. A correctly rounded
result is 0 ULPs away; good libraries promise 1 or 2. Handy fact: for two positive
floats, the difference of their bit patterns read as integers *is* their distance in
ULPs.

## Lesson: masked tails

The last n % 8 elements don't fill a ymm register. `vmaskmovps ymm0, ymm_mask, [m]`
loads only the lanes whose mask element has its top bit set (the others read as 0, and
can't fault), and `vmaskmovps [m], ymm_mask, ymm0` stores only those lanes. One more pass
of the same code, no scalar version needed.

## Gate

`ring_exp(in, out, n)` sets out[i] = e^in[i] for n floats, with −87.3 ≤ in[i] ≤ 88.7.

- Every result within **2 ULPs** of the correctly rounded value.
- Budget: **1 cycle per element**, plus a small fixed allowance. The CPU has AVX2 and
  FMA, and the solution must use FMA (the tests check).
- Nothing written past out[n − 1], and `vzeroupper` before you return.
