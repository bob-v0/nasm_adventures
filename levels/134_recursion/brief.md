# Level 134 — Recursion

*A function that calls itself, and a stack that remembers every unfinished call.*

## Lesson: recursion on a real stack

Every call gets its own **frame**: its return address, plus whatever it pushed. When a
function calls itself, the frames pile up, one per unfinished call, and unwind in
reverse. That's all recursion is to the CPU.

The ABI rules you learned decide what survives:

- values you need **after** a recursive call must be in callee-saved registers (or
  in your frame), not in scratch registers
- since each call saves its caller's callee-saved registers, every level of recursion
  gets its own copies

The stack is finite (8 MB by default on Linux). Deep recursion runs out of it and dies
with a segmentation fault, a **stack overflow**.

## The puzzle

Towers of Hanoi: move a stack of n disks from one peg to another, one disk at a time,
never putting a larger disk on a smaller one. The recursive solution is three lines:

```
hanoi(n, from, to, via):
    if n == 0: return
    hanoi(n - 1, from, via, to)     # get the n - 1 smaller disks out of the way
    move disk n: from -> to
    hanoi(n - 1, via, to, from)     # put them back on top
```

It takes 2ⁿ − 1 moves.

## Gate

Write `hanoi(n, from, to, via, out)` (n ≤ 12; pegs are numbers 1–3; `out` points into
the game's `moves` buffer). Record each move as **two bytes**, the from-peg and the
to-peg, starting at `out`, and return the address just past the last move written
(`out` itself if n = 0).

Constraints: at most 40 instructions; must use `call` (recursively). The contract
applies, and recursion makes it matter.
