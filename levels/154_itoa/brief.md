# Level 154 — Numbers to Text

*The CPU thinks in binary. People read decimal. Every `printf` you have ever called
does what you are about to write.*

## Lesson: digits by division

A register holds the *number* 1234, but to print it you need the four *characters*
`1`, `2`, `3`, `4`. The last decimal digit of x is `x % 10`, and the rest of the
number is `x / 10`. Repeat until nothing is left:

```
1234 % 10 = 4   1234 / 10 = 123
 123 % 10 = 3    123 / 10 = 12
  12 % 10 = 2     12 / 10 = 1
   1 % 10 = 1      1 / 10 = 0   → stop
```

The digits come out **backwards**: 4, 3, 2, 1. Either write them from the end of a
scratch area towards the start and then copy them, or count the digits first. A
digit d becomes the character `'0' + d` (the digit characters are consecutive, from
`'0'` = 48 to `'9'` = 57). Use a do-while loop so that 0 still prints one digit.

`div` is fine here (level 159 showed the faster way). Remember that `div` divides
**rdx:rax**, so zero rdx every time.

## Lesson: the signed trap

For a negative x, print `-` and then the magnitude −x. But −(−2⁶³) doesn't fit in a
signed 64-bit register; it wraps back to −2⁶³. The fix is to treat the magnitude
as **unsigned**: `neg` gives the right bits (2⁶³), and unsigned division handles it.
Many real `itoa` implementations got this wrong.

## Lesson: hex with a table

Each hex digit is 4 bits: `x & 15` picks the lowest, `shr x, 4` drops it. To turn
0–15 into a character, look it up in a **table** instead of writing an `if` for the
letters:

```
digits: db "0123456789abcdef"
    movzx edx, byte [digits + rdx]
```

## Gate

The game provides three 24-byte buffers (filled with `#` by the tests). On entry
`rdi` = x. Write, with no terminator:

| Buffer | Text | Length in |
|---|---|---|
| `dec_u` | x as an unsigned decimal | `rax` |
| `dec_s` | x as a signed decimal (`-` for negatives) | `rbx` |
| `hex` | `0x` + x in lowercase hex, no leading zeros (`0x0` for 0) | `rcx` |

Bytes after each string must stay `#`. `rdi` must be unchanged. Constraint: at most 110
instructions. (No `call` yet, so repeating a loop with small changes is fine.)

When you pass, your solution is saved to your **library** as `itoa`. Once Arc IV
teaches functions, you'll turn it into a routine and reuse it, all the way down to your
kernel's `printk`.
