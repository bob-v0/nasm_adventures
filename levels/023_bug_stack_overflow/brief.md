# Level 23 — Bug: Kernel Stack Overflow ◆◆◆

*A user program that overflows its stack gets a segfault. A kernel that overflows its
stack gets nothing: it just writes over its own data and carries on.*

## Symptoms

The kernel adds up squares, recursively, up to `n` from the command line:

```
sum of squares 1..10 = 385
```

Small n: right. A little larger: a 19-digit number, and no crash, no warning, nothing.

## Background: a fixed, small stack

A user program's stack grows on demand: the kernel maps more pages as it goes down.
A kernel stack is a fixed few KiB, and in this kernel nothing is below it except more
of the kernel's own .bss. Each call of `sum_squares` keeps a 1 KiB buffer on the stack.
Recurse deep enough and the frames land on the `squares` table below. The sum is
then built from whatever the buffers wrote there.

![The stack runs over squares; a guard page turns that into a fault](guard.svg)

## Background: guard pages

The standard defence is a **guard page**: one page right below the stack that is never
mapped. The first write past the bottom is a page fault, not silent corruption.

That page fault happens *on* the broken stack, though, so the CPU can't push its frame:
a second fault, which makes it a **#DF**. Level 24's IST stack is there for exactly this.
The double fault handler runs on a stack of its own and reports. For n too large, the
output should become:

```
sum of squares 1..20 = #DF at 0x…, error code 0x0000000000000000
```

## Gate

Find an n that gives a wrong sum (`;! witness n = N`), then fix it: right sums for small n,
and a #DF report instead of a wrong sum for large ones. At most 8 changed lines.
