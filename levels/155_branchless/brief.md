# Level 155 — Branchless

*The CPU guesses which way every branch goes, long before it knows. When it guesses
wrong, it throws away work. Here you write code with no branches to guess.*

## Lesson: why branches cost

A **branch** is any jump that might or might not be taken. Modern CPUs work far ahead
of the instruction they are currently finishing, like a cook who starts chopping the
next dish before the first is plated. At a conditional jump they don't wait to find
out which way it goes: they **predict** the outcome and carry on speculatively. A
wrong guess costs around 15–20 cycles of discarded work. Unpredictable branches, such
as those that depend on random data, can make code several times slower (Arc VII
measures this).

## Lesson: cmov and setcc

Two instruction families turn flags into data without jumping:

```
cmp rdi, rsi
cmovl rax, rsi     ; if (signed) rdi < rsi: rax = rsi     (no jump)
setg  dl           ; dl = 1 if (signed) rdi > rsi, else 0
```

They use the same condition names as jumps: `cmovb`/`cmova` (unsigned), `cmovl`/`cmovg`
(signed), `cmove`/`cmovne`, `cmovs`, and so on. Together they are written `cmovcc` and
`setcc`, where cc stands for any condition.

Two details to watch:

- `setcc` writes only 8 bits, so zero the full register first. Do it with `xor`
  *before* the `cmp`, because `xor` changes the flags.
- `cmov` can't take an immediate: put constants in registers.

## Gate

On entry `rdi` = a, `rsi` = b. With **no jumps at all**:

| Register | Must hold |
|---|---|
| `rax` | abs(a), the absolute value (signed; abs(−2⁶³) wraps to −2⁶³, as in C) |
| `rbx` | min(a, b), signed |
| `rcx` | max(a, b), unsigned |
| `rdx` | sign(a): −1, 0 or 1 |
| `r8` | 1 if a = b, else 0 |

`rdi` and `rsi` must be unchanged. Constraints: at most 24 instructions; must use
`cmovl`; no `j…` or `loop` instructions.
