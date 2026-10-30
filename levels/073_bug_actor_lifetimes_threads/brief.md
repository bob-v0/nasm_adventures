# Level 73 — Bug: Lifetimes Across Actors ◆◆◆◆

*Level 101 had one thread and a clear owner. Now many threads hold the same actor at the
same time, and it has to be freed by exactly one of them, exactly when the last one lets
go.*

## Symptoms

Level 74's actor system, with actors on the heap. Who keeps an actor alive:

- the **registry**, until shutdown;
- every **sender**, while it's sending to it;
- the **run queue**, from `runq_push` until the worker has finished running it.

Each takes a reference (`get_ref`) and drops it (`put_ref`); the last `put_ref` frees the
actor. Under some schedules the checked allocator finds a use after free (an actor freed
while a worker was still running it), a double free, or leaked actors whose count never
reached zero.

## Background: reference counts across threads

A **reference count** is shared state written by every thread that holds the object,
concurrently. That means two requirements:

1. **Atomic updates.** `inc`/`dec` on memory are read-modify-writes: two threads can lose an
   update (level 89). A lost increment frees too early; a lost decrement leaks.
2. **Decrement-and-test in one step.** `dec [refs]` then `cmp [refs], 0` is check-then-act
   (level 86): between them another thread can decrement too, and *both* see 0 (double
   free), or one sees 0 after the other's decrement while a third has just taken a new
   reference. The question "was mine the last reference?" must be answered by the same
   atomic instruction that drops it: `lock xadd` returns the count *before* your decrement,
   so exactly one thread sees 1.

(On weaker memory models there's a third requirement: **release** ordering on the
decrement and **acquire** before freeing, so that all the other threads' last uses of
the object happen-before the free. On x86, locked instructions are full barriers. This is
what C++'s `shared_ptr` and Rust's `Arc` do.)

## Gate

1. Add a witness: a schedule under which the original frees too early, twice, or never:
   `;! witness schedule = N`.
2. Fix `get_ref` and `put_ref`, changing at most **6 lines**.
