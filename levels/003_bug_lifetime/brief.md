# Level 3 — Bug: Lifetime Across CPUs ◆◆◆◆

*Taking something out of a list doesn't mean nobody is looking at it.*

## Symptoms

The kernel has a list that is read all the time and changed now and then. The other CPUs
walk it again and again, **without a lock**: readers never write it, and making every
reader wait for a lock would make them take turns. The first CPU changes it, 400 times:
it unlinks the second node, frees it, and puts a fresh node in front. Freeing a node
**poisons** it (its magic word becomes 0xDEADDEAD instead of the live one), so a reader
that comes across a freed node can tell, and counts it:

```
updates: 400, freed nodes seen: 16
```

## Background: unlinked isn't unused

![A reader is already on the node when it's unlinked and freed](lifetime.svg)

Once a node is unlinked, no *new* walk can reach it. But a walk that began a moment
earlier may be standing on it: about to read its value, or its `next`. Freeing it now
(and here, reusing it right away) pulls it out from under that reader. The same holds
for a task another CPU is about to switch to, or a page table another CPU still has in
CR3.

The kernel's answer is to wait. Not with a lock, but for a **grace period**: until every
reader has been, at least once, in a state where it holds no node at all. Here that's
between two walks, a **quiescent state**, which each reader counts. After unlinking:
note every reader's count; wait until each one has moved; then free. Any walk that could
have seen the node is over by then.

That's the heart of Linux's **RCU** (read-copy-update): readers pay nothing, and writers
wait.

As in levels 5 and 4, the CPUs run truly in parallel, and the race doesn't show on every
run: the fix must make it impossible, not rare.

## Gate

No freed node is ever seen, on 3 and 4 CPUs, run after run; the readers' code
unchanged. At most 30 changed lines.
