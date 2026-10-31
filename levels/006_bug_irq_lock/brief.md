# Level 6 — Bug: IRQ-Unsafe Lock ◆◆◆

*Two pieces of code, one lock, one CPU. Each waits for the other, forever.*

## Symptoms

The kernel spends nearly all its time working through its log while holding the log's
**lock**. The keyboard's interrupt handler logs each key, so it takes the same lock.

Type a few keys and the kernel freezes, often on the first one. The game shows you where
the CPU is when it gives up: spinning in `lock_log`.

## Background: who holds it?

A spinlock waits for its holder to let go. That works between CPUs: the holder is
running somewhere else and will finish. But here the holder is **the code the interrupt
interrupted, on the same CPU**. The handler spins waiting for it, and it can't run again
until the handler returns:

![The main loop holds the lock; the interrupt handler on the same CPU waits for it](deadlock.svg)

This is one of the classic kernel bugs. The fix is just as classic: while you hold a
lock that an interrupt handler also takes, **keep interrupts off**. Linux calls it
`spin_lock_irqsave`: save the flags, `cli`, take the lock; later release it and restore
the flags. Restoring, not `sti`: the handler takes the lock too, with interrupts already
off, and must leave them that way.

## Gate

Every key logged, in order, and `bye` after Esc, every time. At most 8 changed lines.
