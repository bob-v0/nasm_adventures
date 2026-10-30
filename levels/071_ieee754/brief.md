# Level 71 — IEEE 754

*Arc IX begins with numbers that aren't integers. Before the instructions that compute
with them, the bits: every float and double in every program is the same three fields.*

## Lesson: the layout of a double

A `double` (IEEE 754 binary64) is 64 bits:

```
 63 | 62 ........... 52 | 51 ........................... 0
sign|   exponent e (11)  |          fraction f (52)
```

For most values (**normal** numbers, e from 1 to 2046) the value is

    (−1)^sign × 1.f × 2^(e − 1023)

- **1023** is the exponent **bias**: e = 1023 means 2^0. The field is unsigned; the bias
  makes it signed.
- **1.f**: the leading 1 is **implicit**. Every normal number starts with a 1 in binary,
  so it isn't stored, and the 52 stored bits are all after the point: 53 bits of
  precision.

| value | bits |
|---|---|
| 1.0 | `3FF0000000000000` (e = 1023, f = 0) |
| −2.0 | `C000000000000000` (sign, e = 1024) |
| 0.5 | `3FE0000000000000` (e = 1022) |
| 3.0 | `4008000000000000` (1.1₂ × 2^1) |

A `float` is the same idea in 32 bits: 1 sign, 8 exponent bits (bias 127), 23 fraction bits.

## Lesson: the special exponents

| e | meaning |
|---|---|
| 0, f = 0 | **±0**: there are two zeros, and `-0.0 == 0.0` |
| 0, f ≠ 0 | **denormal** (subnormal): 0.f × 2^−1022, no implicit 1: values smaller than the smallest normal number, with less precision (level 93 met their cost) |
| 2047, f = 0 | **±infinity**: 1/0, overflow |
| 2047, f ≠ 0 | **NaN**, "not a number": 0/0, √−1. The top fraction bit says quiet (1) or signalling (0); the rest is a payload |

## Lesson: converting to an integer

`cvttsd2si rax, xmm0` (next levels) truncates a double toward zero. When the result
doesn't fit in 64 bits, or the input is an infinity or NaN, it doesn't fail: it returns
**0x8000000000000000**, the "integer indefinite" value. With the layout above you can do
the same with shifts: the integer part of 1.f × 2^k is the 53-bit number 1f, shifted.

## Gate

`ring_dtoi(bits)`: rdi holds a double's bits; return what `cvttsd2si` would, using
integer instructions only.
