# Level 63 — Packed Floats

*The same xmm registers, the same idea as level 67, with floats: four multiplications
per instruction.*

## Lesson: packed single and double

`ps` instructions work on four floats ("packed single"), `pd` on two doubles:

| instruction | effect |
|---|---|
| `movaps xmm0, [m]` | load 4 floats, 16-byte aligned (faults otherwise); `movups`: any address |
| `addps`, `subps`, `mulps`, `divps`, `sqrtps`, `minps`, `maxps` | lane by lane |
| `addps xmm0, [m]` | a memory operand must be 16-byte aligned (legacy SSE rule) |
| `xorps xmm0, xmm0` | four zeros |
| `cmpltps xmm0, xmm1` | a mask per lane (level 65's idea, for floats) |
| `movmskps eax, xmm0` | the four sign bits |

## Lesson: horizontal operations

SIMD is fast **vertically** (lane i with lane i). Adding the lanes of one register is a
**horizontal** sum and takes shuffles: `movhlps` brings the high half down, then `shufps`
(or `pshufd`) brings lane 1 to lane 0. `haddps` exists, and is slower than the two
shuffles. Do it once, after the loop, never inside it.

## Lesson: latency again

`addps` takes 4 cycles. A loop where every iteration adds into the same register
waits for the previous one: 4 elements per 4 cycles. Several **accumulators** (level 98)
let four `addps` be in flight at once.

## Lesson: the order of additions

Float addition isn't associative: (a + b) + c can differ from a + (b + c) in the last
bits. Four accumulators add the numbers in a different order than the simple loop, so
the result differs slightly. That's why compilers don't vectorize a float sum unless you
allow it (`-ffast-math`), and why this level accepts any order within a tolerance.
Several accumulators are usually *more* accurate: each adds up fewer numbers.

## Gate

`ring_dot(a, b, n)` for arrays of floats, within **0.6 cycles per element**.
