# Level 166 — Signed vs Unsigned

*The same 64 bits, two different numbers. The CPU tracks both at once.*

## Lesson: two's complement

Unsigned, 64 bits hold 0 … 2⁶⁴−1. **Signed** numbers use **two's complement**: the
top bit counts as −2⁶³ instead of +2⁶³, giving −2⁶³ … 2⁶³−1.

```
bits (8-bit for brevity)   unsigned   signed
0000_0001                       1        1
0111_1111                     127      127
1000_0000                     128     -128
1111_1111                     255       -1
```

To negate: invert all bits and add 1 (`neg` does both). The great property: **`add` and
`sub` give the right bits for both readings**, so the CPU needs only one adder. It
records the two ways a result can be wrong:

- **CF**: the result is wrong as an *unsigned* number (carry out, or borrow).
- **OF**: the result is wrong as a *signed* number. This happens when adding two
  numbers of the same sign gives the other sign.

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
