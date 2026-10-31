# Level 134 — Recursion

*A function that calls itself, and a stack that remembers every unfinished call.*

## Lesson: recursion on a real stack

A **recursive** function is one that calls itself. To the CPU there is nothing
special about it. Every call gets its own **frame**: its return address, plus whatever
it pushed. When a function calls itself, the frames pile up, one per unfinished call,
and unwind in reverse order as the calls return.

The ABI rules you learned decide what survives:

- values you need **after** a recursive call must be in callee-saved registers (or
  in your frame), not in scratch registers: the inner call is free to destroy those
- since each call saves its caller's callee-saved registers, every level of the
  recursion gets its own copies

The stack is finite (8 MB by default on Linux). Recursion that goes too deep runs out
of it and dies with a segmentation fault: a **stack overflow**.

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

Here are the calls for n = 2, from peg 1 to peg 3. Each indented line is a call that
waits for the ones below it:

```
hanoi(2, 1, 3, 2)
    hanoi(1, 1, 2, 3)
        hanoi(0, ...)        returns at once
        move 1 -> 2
        hanoi(0, ...)
    move 1 -> 3
    hanoi(1, 2, 3, 1)
        hanoi(0, ...)
        move 2 -> 3
        hanoi(0, ...)
```

It takes 2ⁿ − 1 moves: 3 here.

## Gate

Write `hanoi(n, from, to, via, out)` (n ≤ 12; pegs are numbers 1–3; `out` points into
the game's `moves` buffer). Record each move as **two bytes**, the from-peg and the
to-peg, starting at `out`, and return the address just past the last move written
(`out` itself if n = 0).

For the example above, the buffer gets the bytes `1 2 1 3 2 3`, and you return
`out + 6`.

Constraints: at most 40 instructions; must use `call` (recursively). The contract
applies, and recursion makes it matter.
