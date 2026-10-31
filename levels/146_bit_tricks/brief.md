# Level 146 — Bit Tricks

*A handful of identities that turn up in allocators, hash tables, schedulers and
kernels. Worth knowing by heart.*

## Lesson: two's complement at work

Since −x = ~x + 1, negating a number flips every bit **above** its lowest set bit and
keeps that bit (and the zeros below it) as they were. Combine the two with `and` and
only that one bit survives:

```
x       = 0101_1000
-x      = 1010_1000
x & -x  = 0000_1000     isolate the lowest set bit        (BMI1: blsi)
x - 1   = 0101_0111
x&(x-1) = 0101_0000     clear the lowest set bit           (BMI1: blsr)
```

Subtracting 1 works from the other side: it turns the lowest set bit into 0 and the
zeros below it into 1s.

So x is a power of two exactly when x ≠ 0 and `x & (x - 1)` is 0: it has a single bit.

## Lesson: powers of two by counting zeros

`lzcnt` counts leading zero bits (the zeros above the highest 1), so `64 - lzcnt(v)`
is the number of bits needed to write v, its **bit length**. The smallest power of
two ≥ x is `1 << bitlength(x - 1)`. For x = 20: x − 1 = 19 = `10011`, 5 bits long, so
the answer is 1 << 5 = 32. Allocators use this to pick size classes, and hash tables
to size their arrays.

## Lesson: parity

The **parity** of x says whether it has an odd number of 1 bits: `popcnt` counts them,
then keep bit 0 of the count. (The PF flag also gives parity, but only of the lowest
byte.)

## Gate

On entry `rdi` = x (never 0, never above 2⁶³), `rsi` = y. With **no jumps**:

| Register | Must hold |
|---|---|
| `rax` | x with only its lowest set bit kept |
| `rbx` | x with its lowest set bit cleared |
| `rcx` | 1 if x is a power of two, else 0 |
| `rdx` | the smallest power of two ≥ x |
| `r8` | the parity of x: 1 if it has an odd number of 1 bits |
| `r9` | abs(x − y), the distance between x and y, as unsigned numbers |

`rdi` and `rsi` must be unchanged. Constraints: at most 26 instructions; no `j…` or
`loop`. Stretch goal: 20 instructions.
