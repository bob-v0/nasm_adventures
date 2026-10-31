# Level 164 — Division

*Division is the slowest arithmetic instruction, the strangest to set up, and the
only one that can crash your program.*

## Lesson: `div` and `idiv`

Division is the mirror image of `mul`. Where `mul` *produces* a 128-bit result in
**rdx:rax**, `div` *starts from* one: it divides the 128-bit value in rdx:rax by its
operand.

```
div rsi       ; unsigned: rax = rdx:rax / rsi, rdx = remainder
idiv rsi      ; signed:   the same, rounding toward zero
```

So before dividing a 64-bit number you must fill in the high half, rdx:

- unsigned: `mov edx, 0` (rdx = 0)
- signed: `cqo` copies the sign bit of rax into all of rdx, making rdx:rax the 128-bit
  version of rax. (`cdq` and `cwd` do the same for eax and ax.)

Forget it, and you divide by whatever garbage rdx happened to hold.

## Lesson: #DE, the divide error

If the divisor is 0, **or the quotient doesn't fit in 64 bits**, the CPU raises a
**divide error (#DE)** and Linux kills the program (with the signal SIGFPE). The
second case surprises people: −2⁶³ / −1 = 2⁶³, which doesn't fit. A non-zero garbage
rdx can have the same effect. The tests here avoid both.

## Lesson: truncation vs floor

When a division isn't exact, the quotient has to be rounded one way or the other.

- `idiv` **truncates** (rounds toward zero), like C.
- Python and mathematics use **floor** (round down, toward −∞), so the remainder
  takes the divisor's sign.

Both satisfy a = q × b + r. They only disagree when the remainder is non-zero and
the signs differ:

| a, b | truncated (C) q, r | floored (Python) q, r |
|---|---|---|
| 7, 2 | 3, 1 | 3, 1 |
| −7, 2 | −3, −1 | −4, 1 |
| 7, −2 | −3, 1 | −4, −1 |

## Gate

On entry `rdi` = a, `rsi` = b (signed, never zero, never −2⁶³ / −1):

| Register | Must hold |
|---|---|
| `r8` | a / b truncated (C) |
| `r9` | a % b truncated (C): same sign as a |
| `rax` | a / b floored (Python `//`) |
| `rdx` | a mod b floored (Python `%`): same sign as b |

`rdi` and `rsi` must be unchanged. Constraints: at most 24 instructions; must use
`idiv` and `cqo`.
