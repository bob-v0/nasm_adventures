# Level 146 — Bit Tricks

*A handful of identities that turn up in allocators, hash tables, schedulers and
kernels. Worth knowing by heart.*

## Lesson: two's complement at work

Since −x = ~x + 1, negating flips every bit **above** the lowest set bit and keeps
that bit:

```
x       = 0101_1000
-x      = 1010_1000
x & -x  = 0000_1000     isolate the lowest set bit        (BMI1: blsi)
x - 1   = 0101_0111
x&(x-1) = 0101_0000     clear the lowest set bit           (BMI1: blsr)
```

So x is a power of two exactly when x ≠ 0 and `x & (x - 1)` is 0: it has a single bit.

## Lesson: powers of two by counting zeros

`lzcnt` counts leading zero bits, so `64 - lzcnt(v)` is the number of bits needed to
write v. The smallest power of two ≥ x is `1 << bitlength(x - 1)`. Allocators use it to
pick size classes, hash tables to size their arrays.

## Lesson: parity

The parity of x is whether it has an odd number of 1 bits: `popcnt` then keep bit 0.
(The PF flag also gives parity, but only of the lowest byte.)

## Gate

On entry `rdi` = x (never 0, never above 2⁶³), `rsi` = y. With **no jumps**:

| Register | Must hold |
|---|---|
| `rax` | x with only its lowest set bit kept |
| `rbx` | x with its lowest set bit cleared |
| `rcx` | 1 if x is a power of two, else 0 |
| `rdx` | the smallest power of two ≥ x |
| `r8` | the parity of x: 1 if it has an odd number of 1 bits |
| `r9` | \|x − y\|, as unsigned numbers |

`rdi` and `rsi` must be unchanged. Constraints: at most 26 instructions; no `j…` or
`loop`. Stretch goal: 20 instructions.
