# Level 137 — Bug: Broken Contract ◆◆

*The library's unit tests pass. Every application that links it crashes, in places
that have nothing to do with the library.*

## Symptoms

`frame` prepends a length byte to a packet and returns a checksum, and its results are
right. But the application that calls it finds its own variables changed after the
call, the helper it calls reports a misaligned stack, and later string operations in
the application run backwards.

## Why bugs like this are nasty

A calling-convention violation doesn't break the function that commits it; it breaks
the **caller**, later, somewhere else. Saved registers hold the caller's loop counters
and pointers. A misaligned stack crashes only when some callee uses aligned SSE
instructions. A leftover DF makes the *next* `rep movsb` in someone else's code go the
wrong way. In C programs these show up as "impossible" crashes in unrelated code.

## How to hunt

Check the function against the contract from levels 140 and 139, one rule at a time:

1. Which callee-saved registers (rbx, rbp, r12–r15) does it write? Are all of them
   saved and restored?
2. Count the pushes: is rsp % 16 == 0 at each `call`?
3. What flags state does it leave? The ABI requires DF = 0 on return.

The game calls it from `ring_app`, which keeps values in callee-saved registers and
checks them after the call.

## Gate

Make `frame` honour the contract, changing at most **3 lines**.
