# Level 182 — Speaking in Numbers

*The gate shows six locks, each labelled in a different notation.*

## Lesson: one value, many spellings

A register holds 64 bits, nothing more. Whether you write `200`, `0xC8` or
`0b1100_1000` in your source makes no difference to the CPU: NASM turns all three
into the same bits. So pick the notation that makes your *intent* easiest to see:

| Base | Digits | Good for |
|---|---|---|
| binary (2) | 0 1 | flags, masks, single bits |
| octal (8) | 0–7 | Unix file permissions |
| decimal (10) | 0–9 | counts, human-facing numbers |
| hexadecimal (16) | 0–9 A–F | addresses, bytes, anything bit-shaped |

Hex is the programmer's favourite because each hex digit stands for exactly 4 bits,
so two hex digits make exactly one byte. You can read the bits straight off it:
`0xC8` is `1100` `1000`.

## Lesson: how NASM writes numbers

```
200                 decimal
0xC8   0C8h         hex (with the h suffix the first character must be a digit,
                    otherwise C8h would be read as a label)
0o310  310q         octal
0b1100_1000         binary; underscores can go anywhere in any number
'A'                 character constant = 0x41
'AB'                = 0x4241. Characters fill the LOW bytes first, so
                    when stored to memory they appear in order "A","B".
-1                  two's complement: all 64 bits set (level 166 explains this)
```

The decimal, hex, octal and binary examples all spell the same number, 200.

`mov` into a 64-bit register accepts a full 64-bit constant. NASM picks the shortest
encoding that gives the same result, and {{listing}} shows you which one it chose.

## Gate

When your code finishes:

| Register | Must hold |
|---|---|
| `rax` | the bit pattern `10101010` repeated eight times (64 bits) |
| `rbx` | the character constant made of the four letters `N`, `A`, `S`, `M` |
| `rcx` | minus one |
| `rdx` | the Unix permission mode `755`, read as octal |
| `rsi` | one trillion (10¹²) |
| `rdi` | the hex value `BEEF`, written with the `h` suffix (for practice; the gate only checks the value) |

Constraint: at most 6 instructions.

## Try this

In {{debug}}, step to the end and read each register in hex.
`0xAAAA_AAAA_AAAA_AAAA` and your binary pattern are the same bits.
