# Level 163 — Bug: Signed or Unsigned? ◆

*The code compiles, the tests with small positive numbers pass, and it has been in
production for months. Then a customer enters a negative number.*

## Symptoms

The routine computes a signed maximum, a signed quotient, and adds a signed byte
offset. With positive inputs everything looks right. With a negative `a`, `b` or
`delta`, all three results can be wrong, and not in an obvious way: you get huge
numbers, not just wrong signs.

## What to look for

Many x86 operations come in **signed** and **unsigned** versions, and the CPU happily
runs whichever one you wrote:

| Operation | unsigned | signed |
|---|---|---|
| compare and jump | `ja`, `jb`, `jae`, `jbe` | `jg`, `jl`, `jge`, `jle` |
| divide | `mov edx, 0` + `div` | `cqo` + `idiv` |
| widen | `movzx` | `movsx`, `movsxd` |
| shift right (next arc level) | `shr` | `sar` |

`add`, `sub`, `imul` with two or three operands, and `cmp` itself are the same for
both, so they are never the bug.

## How to hunt

Test with **boundary values**: −1, 0, 1, the most negative and most positive
numbers, and bytes 0x7F / 0x80. In the debugger, run the failing test and compare each
intermediate value with what you'd compute by hand.

## Gate

Make all three results correct for any signed inputs, changing at most **4 lines**.
