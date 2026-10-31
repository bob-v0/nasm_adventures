# Level 89 — Bug: Data Race ◆◆

*The statistics are always a little low. Never by much, never the same amount twice,
and never when you're watching.*

## Symptoms

A server keeps two counters: requests handled and bytes sent. Four worker threads each
handle 40 requests of 160 bytes, so at the end the totals should be
`hits 160 bytes 25600`. Run it once and they may well be. Under other schedules they come
out a few short.

## Background: data races

A **data race** is two threads accessing the same memory location at the same time, at
least one of them writing, with nothing (no lock, no atomic operation) putting the
accesses in order. `inc qword [hits]` is a read, an add and a write. Two cores running
it at once both read the same old value and both write old + 1. That's a lost update:
the textbook race, and level 90's lesson seen from the bug's side.

What makes races vicious:

- They depend on **timing**. Most runs are fine; a slightly different interleaving loses
  updates. Adding a print to debug it changes the timing, and the bug hides.
- In C and C++ a data race is **undefined behaviour**: the compiler may assume it never
  happens, and transform the code in ways that make things far stranger than a lost
  update.
- Tools can find them even in runs where nothing visibly breaks: ThreadSanitizer,
  Helgrind, Go's `-race`.

## How the game tests it

Each test runs the program under the plain schedule and under many others, with real
x86 store buffers in the model. Every schedule must print the right totals.

## Gate

1. Add a witness: a schedule under which the original prints wrong totals:
   `;! witness schedule = N`.
2. Fix it, changing at most **2 lines**.
