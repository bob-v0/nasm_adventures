# Level 63 — Packed Floats

*The same xmm registers, the same idea as level 67, with floats: four multiplications
per instruction.*

## Lesson: packed single and double

The `ps` instructions ("packed single") work on four floats at once, the `pd` ones
("packed double") on two doubles:

| instruction | effect |
|---|---|
| `movaps xmm0, [m]` | load 4 floats from a 16-byte aligned address (faults otherwise); `movups`: any address |
| `addps`, `subps`, `mulps`, `divps`, `sqrtps`, `minps`, `maxps` | lane by lane |
| `addps xmm0, [m]` | a memory operand must be 16-byte aligned (legacy SSE rule) |
| `xorps xmm0, xmm0` | four zeros |
| `cmpltps xmm0, xmm1` | a mask per lane (level 65's idea, for floats) |
| `movmskps eax, xmm0` | the four sign bits |

## Lesson: horizontal operations

SIMD is fast **vertically**: lane i with lane i of another register. Adding up the lanes
of *one* register is a **horizontal** sum, and that takes shuffles:

```
xmm0 = [ d | c | b | a ]           (lane 3 ... lane 0)
movhlps xmm1, xmm0   ->  xmm1 low half = [ d | c ]
addps   xmm0, xmm1   ->  lanes 1,0 = [ b+d | a+c ]
shufps  (lane 1 down) and addss  ->  lane 0 = a+b+c+d
```

`haddps` exists, and is slower than the two shuffles. Either way, do it once, after the
loop, never inside it.

## Lesson: latency again

`addps` has a **latency** of 4 cycles: its result is ready 4 cycles after it starts. A
loop where every iteration adds into the same register must wait for the previous add,
so it does 4 elements per 4 cycles. Several **accumulators** (level 98) let four
`addps` be in flight at once.

## Lesson: the order of additions

Float addition isn't associative: (a + b) + c can differ from a + (b + c) in the last
bits. Four accumulators add the numbers in a different order than the simple loop, so
the result differs slightly. That's why compilers don't vectorize a float sum unless you
allow it (`-ffast-math`), and why this level accepts any order within a tolerance.
Several accumulators are usually *more* accurate: each one adds up fewer numbers.

## Gate

`ring_dot(a, b, n)` returns, as a float in xmm0, the dot product
a[0]·b[0] + ... + a[n−1]·b[n−1] of two 16-byte aligned arrays of n floats. The result
must be within 1e−4 of the exact value, relative to the sum of |a[i]·b[i]|.

Budget: **0.6 cycles per element**, plus a small fixed allowance.
