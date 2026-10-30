# Level 182 — Speaking in Numbers

*The gate shows six locks, each labelled in a different notation.*

## Lesson: bases

A register is just 64 bits. How you write a number in your source code doesn't
matter to the CPU; NASM turns it into bits either way. Pick the notation that
makes the bits easiest to see:

| Base | Digits | One hex digit = | Used for |
|---|---|---|---|
| binary (2) | 0 1 | 4 bits | flags, masks, single bits |
| octal (8) | 0–7 | – | Unix file permissions |
| decimal (10) | 0–9 | – | counts, human-facing numbers |
| hexadecimal (16) | 0–9 A–F | 4 bits exactly | addresses, bytes, anything bit-shaped |

Two hex digits make exactly one byte, so programmers use hex all the time.

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
-1                  two's complement: all 64 bits set (level 167 explains this)
```

`mov` with a 64-bit register takes a full 64-bit constant. NASM uses the shortest
encoding that gives the same result, which {{listing}} shows.

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
