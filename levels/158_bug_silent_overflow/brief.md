# Level 158 — Bug: Silent Overflow ◆◆

*The check says the request is small. The request is for more memory than exists.*

## Background

Code that allocates memory often computes `count × size + header` and checks the total
against a limit. If the multiplication **wraps around**, an enormous request turns into
a tiny number. It passes the check, the program allocates a tiny buffer, and then it
writes `count × size` bytes into it, far past the end. This exact bug has caused real
security vulnerabilities in image decoders, memory allocators and kernels.

## Symptoms

The routine rejects ordinary large requests correctly (try 100 000 × 64). But for some
inputs whose true total is astronomically large, it returns a small "total" and accepts
the request.

## New: witnesses

From now on some bug levels ask you to **prove** the bug before fixing it. A
**witness** is an input that makes the original program give a wrong answer. Put a
line like this in your solution:

```
;! witness rdi = 0x1234, rsi = 5
```

The game runs the **original** program with your witness input and checks that it gets
the wrong answer. Then it runs **your fixed** program with the same input and checks
that it gets the right one. A witness that doesn't break the original doesn't count,
so you have to understand the bug to find one.

## What to look for

- The CPU sets CF/OF when a result doesn't fit, but nothing stops the program from
  carrying on with the wrapped value. Only an explicit check does.
- `imul r, r` reports **signed** overflow. Sizes are **unsigned**.
- Every arithmetic step can wrap, not only the multiplication.

## Gate

1. A witness (`rdi` = count, `rsi` = size) for which the original returns a wrong result.
2. A fix, changing at most **4 lines**, that returns `count × size + 16` when it is at
   most LIMIT and −1 otherwise, computed exactly as if registers had infinite precision.
