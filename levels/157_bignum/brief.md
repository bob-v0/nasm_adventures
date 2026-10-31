# Level 157 — Bignum ★

*The last gate of Arc II asks for a number too big for any register: the product of
two numbers of up to 512 bits each.*

## Lesson: schoolbook multiplication

A **bignum** is a number stored as an array of limbs (64-bit "digits", as in level
168). Multiply two of them the way you learned on paper. In decimal, 23 × 45 is
3×5, 2×5, 3×4 and 2×4, each written in the right column, then added up. With limbs
it looks like this:

```
                         a1      a0
                    ×    b1      b0
        -------------------------------
                    [a0×b0 high][a0×b0 low]
            [a1×b0 high][a1×b0 low]
            [a0×b1 high][a0×b1 low]
    [a1×b1 high][a1×b1 low]
    -----------------------------------
       p3        p2        p1        p0
```

Every partial product `A[i] × B[j]` (128 bits, from `mul`) lands in limbs `i+j` and
`i+j+1`, and adding it can carry further up. An n-limb number times an m-limb number
has at most n + m limbs.

The usual way to organise it: for each i, walk j upwards with a running **carry**:

```
carry = 0
for j in 0 .. m-1:
    (hi, lo) = A[i] * B[j] + product[i+j] + carry     // never overflows 128 bits
    product[i+j] = lo
    carry = hi
product[i+m] = carry
```

## Lesson: loops from jumps

Arc III teaches loops properly, but you already have everything they need: a counter
register, `inc`, `cmp`, and a conditional jump back to a label. Nested loops are two
counters. Use the debugger's step-back to see where a carry goes missing.

## Gate ★

The game provides little-endian limb arrays (limb 0 is least significant):

- `numA`: `rsi` = n limbs (1–8)
- `numB`: `rcx` = m limbs (1–8)
- `product`: 16 limbs of space, **full of garbage**

Write the n + m limbs of A × B into `product`. Limbs beyond n + m must be left
untouched. `rsi` and `rcx` must be unchanged.

Constraints: at most 60 instructions; must use `mul` and `adc`; no division. Each test
gets 20 000 executed instructions.
