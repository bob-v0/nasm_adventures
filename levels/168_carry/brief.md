# Level 168 — The Carry Flag

*Sixty-four bits are not enough. They never were.*

## Lesson: carrying, like in school

To add 58 + 67 on paper, you add the right column first: 8 + 7 = 15. You write
down 5 and **carry** the 1 into the next column, so that column is 5 + 6 + 1 = 12.

The CPU can do the same with numbers wider than a register. Each register-sized
piece, a 64-bit "digit", is called a **limb**. A 128-bit number is two limbs, high
and low:

```
        A = ahi : alo
      + B = bhi : blo
      ---------------
  add  lo  = alo + blo          CF = 1 if it overflowed
  adc  hi  = ahi + bhi + CF     add with carry
```

![Add the low limbs with add, which sets CF; then adc adds the high limbs plus CF](carry-chain.svg)

`adc` (add with carry) adds its operands **plus CF**. `sbb` (subtract with borrow)
subtracts its source **and CF**, so `sub` followed by `sbb` subtracts two-limb
numbers. The final CF tells you whether the whole 128-bit result overflowed (or
borrowed).

Anything between the two steps that changes CF breaks the chain. `mov` and `lea`
never touch flags. `inc` and `dec` don't touch CF either, which is why they used to
be handy in multi-limb loops. `clc` and `stc` clear and set CF directly.

## Gate

Two 128-bit numbers arrive in pairs of registers (high : low):

- A = `rsi` : `rdi`
- B = `rcx` : `rdx`

When your code finishes (all mod 2¹²⁸):

| Registers | Must hold |
|---|---|
| `r9` : `r8` | A + B |
| `r11` : `r10` | A − B |
| CF | 1 if A − B borrowed (A < B as unsigned 128-bit numbers), else 0 |

The inputs must be unchanged. Constraints: at most 10 instructions; must use `adc` and
`sbb`. Stretch goal: 8 instructions.
