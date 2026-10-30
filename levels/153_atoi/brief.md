# Level 153 — Text to Numbers

*Every number that enters a program from outside arrives as text, and some of that
text is written by someone hoping your parser has a bug.*

## Lesson: parsing with a cursor

Keep a pointer to the current character, look at it, decide, and advance:

```
    movzx edx, byte [rsi]   ; current character (zero-extended!)
    test dl, dl
    jz .end                 ; NUL: end of string
    ...
    inc rsi                 ; next character
```

A decimal digit `c` has the value `c - '0'`. Accumulate left to right:
`value = value × base + digit`.

## Lesson: untrusted input

A parser must **reject** what it doesn't understand instead of guessing, and must
notice when a number is **too big** instead of silently wrapping (you saw what
wrapping does in level 158). Overflow can happen at the multiply *or* the add, and
both set CF when done with unsigned arithmetic.

Signed ranges are asymmetric: the magnitude limit is 2⁶³ − 1 for positive numbers and
2⁶³ for negative ones. Accumulate the magnitude as unsigned, check the limit for the
sign at the end, then negate.

## Gate

The game provides `text`: a NUL-terminated string (at most 47 characters). The format:

- optional `+` or `-`
- then **either** decimal digits **or** `0x`/`0X` followed by hex digits (either case)
- then the end of the string. Nothing else is allowed: no spaces, no second sign.

| Result | `rax` | `rbx` (status) |
|---|---|---|
| valid and fits in a signed 64-bit integer | the value | 0 |
| invalid (any bad character, or no digits) | 0 | 1 |
| valid but out of range | 0 | 2 |

An invalid string is status 1 even if it is also huge. Constraint: at most 90
instructions. Passing adds `atoi` to your **library**.
