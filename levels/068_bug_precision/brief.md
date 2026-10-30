# Level 68 — Bug: Precision Lost ◆◆

*The formula is right. It's in every textbook. It's wrong in floating point.*

## Symptoms

`ring_hit` is the ray tracer's ray-sphere intersection: the hits are the roots of
a·t² + b·t + c = 0, and the starter uses the formula from school,
(−b ± √(b² − 4ac)) / 2a. Spheres in the middle of the scene are fine. Tiny spheres far
away are drawn in the wrong place, sometimes at distance 0. And a scene with a broken
(NaN) coordinate draws nothing, silently, instead of being reported.

## Background: rounding error

Every floating-point operation rounds its exact result to 53 significant bits: a
**relative error** of at most 2^−53 ≈ 1.1e−16. That's tiny, and it stays tiny through
multiplication, division and square roots, and through additions of numbers with the
same sign.

## Background: catastrophic cancellation

Subtraction of two nearly equal numbers is exact, and that's the problem: the result
keeps only the digits where they differ, and those are exactly the digits the earlier
roundings already damaged. 1.0000000000000002 − 1.0 = 2.2e−16: one significant bit
left, all of it noise. When the inputs carry rounding error, the difference can be
100 % error. That's **catastrophic cancellation**.

The cure is algebra: rewrite the formula so the subtraction never happens. For
example √(x+1) − √x is better as 1 / (√(x+1) + √x).

## Background: NaN and the flags

`ucomisd` has four outcomes: less (CF), equal (ZF), greater (neither) and **unordered**,
when either side is a NaN, which sets **ZF, PF and CF together**. So with a NaN, `jb`
is taken, `je` is taken, `jbe` is taken. Code that branches on a compare without first
asking `jp` treats NaN as whatever its first branch says. (`x == 0.0` exact equality is
fine when you mean exactly 0, as here: d = 0 only happens for exact tangents.)

## Gate

Find an input that breaks the original (`;! witness a = "…", b = "…", c = "…"`), then fix
both bugs: hits accurate to 12 significant digits for every non-grazing ray, and −1 for
NaN inputs. At most 30 changed lines.
