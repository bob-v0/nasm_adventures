# Level 4 — Bug: TLB Shootdown Race ◆◆◆◆

*The page table already says the new frame. One CPU still reads the old one, and someone
is writing into it.*

## Symptoms

Level 5's shootdown, put to work. A page, WINDOW, shows one of two frames, taking
turns. Each round the first CPU fills the frame WINDOW *isn't* showing with the round's
number (all of it), points WINDOW there, and shoots the old translation down. The
old frame is then free, and next round it's filled again.

Every other CPU keeps taking snapshots of WINDOW (interrupts off, the whole page) and
counts the ones that aren't all one number:

```
rounds: 300, torn reads: 162
```

How can a page that's only ever written while nobody is supposed to be looking at it
look half-written?

## Background: sent is not done

![The frame is reused while another CPU's stale translation still points at it](reuse.svg)

An IPI is delivered when the target can take it. A CPU with interrupts off, in the middle
of a snapshot, takes it only after the snapshot. Until then its TLB still says WINDOW =
the old frame, whatever the page table says now. A shootdown is finished only when every
CPU has **acknowledged** it. Freeing (or reusing) the old frame before that is a
**use-after-free across CPUs**: the bug is in the kernel's memory, not in any one CPU.

The game runs these tests with the CPUs truly in parallel, so the race really races. A
fix has to hold on every run, not only on the lucky ones.

## Gate

No torn reads, on 4, 6 and 8 CPUs. At most 6 changed lines.
