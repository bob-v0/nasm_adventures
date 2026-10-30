# Level 165 — Multiplication

*Multiplying two 64-bit numbers gives a 128-bit number. Where does the rest go?*

## Lesson: `mul` (unsigned)

`mul` has **one** explicit operand. The other is always `rax`, and the full result goes
into **rdx:rax** (high : low):

```
mov rax, rdi
mul rsi          ; rdx:rax = rax * rsi   (unsigned, 128-bit result)
```

These **implicit operands** catch everyone: `mul` silently overwrites `rdx`. CF and OF
are set if the high half (rdx) is non-zero.

## Lesson: `imul` (signed), three forms

```
imul rsi              ; rdx:rax = rax * rsi, signed (like mul)
imul r10, rsi         ; r10 = r10 * rsi, low 64 bits only
imul r9, rdi, 37      ; r9 = rdi * 37, low 64 bits only
```

The two- and three-operand forms are the everyday ones: any registers, no rdx surprise.
They set CF and OF when the **signed** result didn't fit in 64 bits.

A nice fact: the **low** 64 bits of a product are the same whether you read the inputs
as signed or unsigned, so `imul r, r` also works for unsigned multiplication when you
only keep 64 bits. Only the high half and the overflow flags differ.

## Gate

On entry `rdi` = a, `rsi` = b. When your code finishes:

| Register | Must hold |
|---|---|
| `rdx` : `rax` | a × b as unsigned, full 128 bits |
| `r10` | the low 64 bits of a × b |
| `r8` | 1 if a × b doesn't fit in 64 bits as a **signed** product, else 0 |
| `r9` | a × 37 (low 64 bits) |

`rdi` and `rsi` must be unchanged. Constraints: at most 14 instructions; must use `mul`
and `imul`.
