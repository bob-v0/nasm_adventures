# Level 31 — Bug: Interrupt Reentrancy ◆◆◆

*There is only one CPU, one thread, and no locks. The bug is still a race.*

## Symptoms

An interrupt handler produces data and the main loop consumes it, like level 32's
keyboard. Here the producer is the APIC timer: every `period` cycles its handler adds the
next number (1, 2, ... 1000) to a 16-slot buffer. The main loop takes them out and checks
each is one more than the last. With some timer periods it works perfectly. With others,
numbers go missing or come back twice.

## Background: interrupts are concurrency

An interrupt can arrive between **any** two instructions of the main code. On one CPU
that's the only way things interleave, and it has two consequences:

- A **single instruction** is atomic with respect to interrupts: `inc dword [x]` can't be
  split by one (on one CPU; across CPUs it can, Arc VIII).
- A **sequence** isn't: `mov ecx, [x]` ... `mov [x], ecx` can have a whole handler run in the
  middle, and whatever the handler wrote to x is overwritten with the stale copy. That's
  level 89's lost update again, with a handler instead of a second thread.

Two classic cures:

- a **critical section**: `cli` before the sequence, `sti` after, so no interrupt can land
  in it (keep it a few instructions long: interrupts wait meanwhile);
- **one writer per variable**: the handler only writes the producer's index, the main loop
  only the consumer's, as in level 32's ring buffer. Nothing is read-modify-written by both.

## Background: hunting it

Whether an interrupt lands in the bad spot depends on timing. The game runs the kernel
with the timer period from the command line (`period=N`) and tries many periods, so the
interrupts move across every instruction of the loop. QEMU's instruction counting makes
each run exactly repeatable: a failing period always fails.

## Gate

Find a period that breaks the original (`;! witness period = N`), then fix it for every
period the game tries. At most 12 changed lines.
