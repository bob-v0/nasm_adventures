# Level 170 — Add & Subtract

*Arc II begins. The machine finally does arithmetic, and its numbers have edges.*

## Lesson: two-operand arithmetic

In most languages you write `c = a + b`. x86 arithmetic has only two operands, and
the result **overwrites the first one**:

```
add rax, rsi      ; rax = rax + rsi
sub rax, rdx      ; rax = rax - rdx
inc rcx           ; rcx = rcx + 1
dec r8            ; r8  = r8 - 1
neg rbx           ; rbx = 0 - rbx
```

So to compute `a + b` without destroying `a`, copy it first: `mov rax, rdi`, then
`add rax, rsi`.

Either operand can be memory (`add [counter], rax`), but not both. A constant
operand (an **immediate**) is at most 32 bits, sign-extended to 64 bits.

## Lesson: numbers wrap around

A 64-bit register can hold 2⁶⁴ different values and no more. When a result goes past
the end, it **wraps around** to the other end, like a car's odometer rolling over.
Mathematicians call this arithmetic **modulo 2⁶⁴**:

```
0xFFFF_FFFF_FFFF_FFFF + 1  =  0           (no error, no exception)
0 - 1                      =  0xFFFF_FFFF_FFFF_FFFF
```

The CPU doesn't decide whether a bit pattern is "signed" or "unsigned". The same
`add` works for both, which is the beauty of two's complement (level 166). Whether a
result "went wrong" is recorded in the **flags**, the subject of the next level.

## Gate

On entry `rdi` = a, `rsi` = b, `rdx` = c. When your code finishes (all mod 2⁶⁴):

| Register | Must hold |
|---|---|
| `rax` | a + b − c |
| `rbx` | −a |
| `rcx` | c + 1 |
| `r8` | b − 1 |
| `r9` | c − 2a |

`rdi`, `rsi` and `rdx` must be unchanged. Constraints: at most 14 instructions; no
`lea`, `mul` or `imul` (they come later).
