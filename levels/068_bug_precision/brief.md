# Level 68 — Bug: Precision Lost ◆◆

*The formula is right. It's in every textbook. It's wrong in floating point.*

## Symptoms

`ring_hit` is the ray tracer's ray-sphere intersection. A ray hits a sphere at the
distances t that solve a·t² + b·t + c = 0, and the starter uses the formula from school:
(−b ± √(b² − 4ac)) / 2a.

- Spheres in the middle of the scene are drawn fine.
- Tiny spheres far away are drawn in the wrong place, sometimes at distance 0.
- A scene with a broken (NaN) coordinate draws nothing, silently, instead of being
  reported.

## Background: rounding error

Every floating-point operation rounds its exact result to 53 significant bits. That's a
**relative error** (error divided by the size of the value) of at most 2^−53 ≈ 1.1e−16.
It stays that tiny through multiplication, division and square roots, and through
additions of numbers with the same sign.

## Background: catastrophic cancellation

Subtracting two nearly equal numbers is exact, and that's the problem. The result keeps
only the digits where they differ, and those are exactly the digits the earlier
roundings already damaged.

Example: 1.0000000000000002 − 1.0 = 2.2e−16. One significant bit is left, and if the
first number carried rounding error, that bit is noise: the difference can be 100 %
error. That's **catastrophic cancellation**.

The cure is algebra: rewrite the formula so the subtraction never happens. For example,
√(x+1) − √x is better computed as 1 / (√(x+1) + √x).

## Background: NaN and the flags

`ucomisd` has four outcomes: less (CF), equal (ZF), greater (neither), and
**unordered**, when either side is a NaN, which sets **ZF, PF and CF together**. So with
a NaN, `jb` is taken, `je` is taken, `jbe` is taken. Code that branches on a compare
without first asking `jp` treats a NaN as whatever its first branch says.

(Exact equality with 0.0 is fine when you really mean exactly 0, as here: the
discriminant is 0 only for an exact graze.)

## Gate

1. Find an input that breaks the original, and write it as a witness line:
   `;! witness a = "…", b = "…", c = "…"` (three numbers as strings; a nonzero, none
   infinite, and not a nearly grazing ray).
2. Fix both bugs. For every non-grazing ray, the hits must be accurate to 12
   significant digits; for any NaN input, return −1.

At most 30 changed lines.
