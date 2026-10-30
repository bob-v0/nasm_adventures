# Level 167 — Compare & Jump

*Until now your programs ran straight through. Now they can choose.*

## Lesson: cmp and conditional jumps

`cmp a, b` computes `a - b`, sets the flags, and throws the result away. A
**conditional jump** then reads the flags and either jumps to a label or falls
through to the next line:

```
    cmp rax, rsi
    jge .big_enough      ; jump if rax >= rsi (signed)
    mov rax, rsi         ; only runs when rax < rsi
.big_enough:
```

`test a, b` is the same idea for `and` (level 162). `test rax, rax` is the usual way
to ask "is rax zero?" (`jz`) or "is it negative?" (`js`).

## Lesson: two families of conditions

The same bits mean different numbers depending on how you read them, so x86 has two
sets of comparisons:

| Meaning | signed (uses SF, OF) | unsigned (uses CF) |
|---|---|---|
| a < b | `jl` (less) | `jb` (below) |
| a ≤ b | `jle` | `jbe` |
| a > b | `jg` (greater) | `ja` (above) |
| a ≥ b | `jge` | `jae` |
| a = b / a ≠ b | `je` / `jne` | `je` / `jne` |

`0xFFFF_FFFF_FFFF_FFFB` is −5 to `jl` and about 1.8 × 10¹⁹ to `jb`. **The CPU doesn't
know which you mean; your choice of jump says it.** `jmp` jumps unconditionally.

## Lesson: local labels

A label that starts with a dot is **local** to the last ordinary label: `.done` after
`clamp:` is really `clamp.done`. You can reuse `.done` in every function without
clashes. In fragment levels your code has no label of its own, so use names like
`.s1` freely.

## Gate

On entry `rdi` = x, `rsi` = lo, `rdx` = hi (lo ≤ hi, both non-negative). Clamp x into
[lo, hi] two ways:

| Register | Must hold |
|---|---|
| `rax` | clamp(x, lo, hi), comparing as **signed** numbers |
| `rbx` | clamp(x, lo, hi), comparing as **unsigned** numbers |

The inputs must be unchanged. Constraints: at most 16 instructions; no `cmov` (Arc III
teaches branch-free code).
