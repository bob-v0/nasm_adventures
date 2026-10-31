# Level 71 — IEEE 754

*Arc IX begins with numbers that aren't integers. Before the instructions that compute
with them, the bits: every float and double in every program is the same three fields.*

## Lesson: the layout of a double

A `double` (the IEEE 754 **binary64** format) is a 64-bit pattern split into three fields:

```
 63 | 62 ........... 52 | 51 ........................... 0
sign|   exponent e (11)  |          fraction f (52)
```

![A double's three fields, and 3.0 decoded](double.svg)

For most values, the **normal** numbers (e from 1 to 2046), the value is

    (−1)^sign × 1.f × 2^(e − 1023)

Two ideas make this work:

- **The bias, 1023.** The exponent field is stored unsigned, but exponents must go
  negative too. So the stored e is the real exponent plus 1023: e = 1023 means 2^0,
  e = 1022 means 2^−1.
- **The implicit 1.** In binary, every normal number starts with a 1 (like 1.1₂ × 2^1
  for 3.0). Since it's always there, it isn't stored. The 52 fraction bits are the digits
  *after* the point, so you get 53 bits of precision.

Worked example: 3.0 is 1.1₂ × 2^1. Sign 0, e = 1 + 1023 = 1024, fraction 1000…0₂.

| value | bits |
|---|---|
| 1.0 | `3FF0000000000000` (e = 1023, f = 0) |
| −2.0 | `C000000000000000` (sign, e = 1024) |
| 0.5 | `3FE0000000000000` (e = 1022) |
| 3.0 | `4008000000000000` (1.1₂ × 2^1) |

A `float` is the same idea in 32 bits: 1 sign bit, 8 exponent bits (bias 127), 23
fraction bits.

## Lesson: the special exponents

The smallest and largest exponent fields are reserved for values the formula can't
express:

| e | meaning |
|---|---|
| 0, f = 0 | **±0**: there are two zeros, and `-0.0 == 0.0` |
| 0, f ≠ 0 | **denormal** (subnormal): 0.f × 2^−1022, no implicit 1. These fill the gap between 0 and the smallest normal number, with less precision (level 93 met their cost) |
| 2047, f = 0 | **±infinity**: 1/0, overflow |
| 2047, f ≠ 0 | **NaN**, "not a number": 0/0, √−1. The top fraction bit says quiet (1) or signalling (0); the rest is a payload |

## Lesson: converting to an integer

`cvttsd2si rax, xmm0` (coming in the next levels) **truncates** a double toward zero:
2.75 becomes 2, −2.75 becomes −2. When the result doesn't fit in a signed 64-bit integer,
or the input is an infinity or a NaN, it doesn't fail. It returns **0x8000000000000000**,
the "integer indefinite" value.

You can do the same with integer shifts. The integer part of 1.f × 2^k is the 53-bit
number "1 followed by f", shifted into place.

## Gate

`ring_dtoi(bits)`: rdi holds a double's bits. Return in rax exactly what `cvttsd2si`
would: the value truncated toward zero as a signed 64-bit integer, or 0x8000000000000000
when it doesn't fit or is an infinity or a NaN.

Use integer instructions only: no x87, SSE or AVX instructions (the tests check).
