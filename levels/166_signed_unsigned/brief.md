# Level 166 — Signed vs Unsigned

*The same 64 bits, two different numbers. The CPU tracks both at once.*

## Lesson: two's complement

Read as **unsigned**, 64 bits hold 0 … 2⁶⁴−1. To store negative numbers too, x86
uses **two's complement**: the top bit counts as −2⁶³ instead of +2⁶³, which gives
the **signed** range −2⁶³ … 2⁶³−1. In 8 bits it looks like this:

```
bits (8-bit for brevity)   unsigned   signed
0000_0001                       1        1
0111_1111                     127      127
1000_0000                     128     -128
1111_1111                     255       -1
```

Picture the 256 byte values on a wheel. Adding 1 moves one step clockwise. The
unsigned reading jumps between 255 and 0; the signed reading jumps between 127 and
−128, on the opposite side.

![A byte's 256 values on a wheel: unsigned wraps between 255 and 0 (CF), signed wraps between +127 and −128 (OF)](twos-complement-wheel.svg)

To negate a number: invert all its bits and add 1 (`neg` does both). The great
property of this scheme is that **`add` and `sub` give the right bits for both
readings**, so the CPU needs only one adder. It records the two ways a result can be
wrong:

- **CF**: the result is wrong as an *unsigned* number (carry out, or borrow). On the
  wheel, it crossed the seam between 255 and 0.
- **OF**: the result is wrong as a *signed* number: it crossed the seam between 127
  and −128. This happens when adding two numbers of the same sign gives the other
  sign.

`jc`/`jnc` and `jo`/`jno` jump on them; `js` jumps if the result is negative.

## Gate

On entry `rdi` = a, `rsi` = b. Set each output to **1 if true, 0 if false**:

| Register | True when |
|---|---|
| `rax` | a + b overflows as **unsigned** |
| `rbx` | a + b overflows as **signed** |
| `rcx` | a − b overflows as **unsigned** (borrows) |
| `rdx` | a − b overflows as **signed** |
| `r8` | a < b as **signed** numbers |
| `r9` | a < b as **unsigned** numbers |

`rdi` and `rsi` must be unchanged. Constraints: at most 40 instructions; no `setcc`,
`pushf` or `lahf` (Arc III gives you `setcc`). Use jumps or the `adc` trick from the
hints.
