# Level 52 — Bug: Stale Code ◆◆◆

*Every JIT recompiles hot code while it runs. The old version doesn't disappear when you
install the new one: someone may still be in it.*

## Symptoms

A tiered JIT in miniature. Two threads share some code memory:

- The **worker** calls `hot(x) = 3x + 1` three hundred times and adds up the results. It
  calls through a **trampoline**: a single `jmp rel32` in code memory that points at the
  current version.
- The **compiler** writes version 2 into buffer 1 and points the trampoline at it. Then
  it writes version 3 into buffer 0, where version 1 was, and points the trampoline
  there.

Every version computes the same thing, so the total should be 134 850. Under some
schedules it's a few short. Under others the worker crashes somewhere in code memory.

## Background: patching live code

Code is data, and another thread may be executing it while you write it. This is
**cross-modifying code**, and it has three problems.

**1. Torn patches.** An instruction is several bytes. If they're written by several
stores, another thread can run a mix of old and new bytes. x86 guarantees that an
aligned store of up to 8 bytes is seen whole, so patch sites are laid out so that the
part to change (here the rel32) can be written by **one** store. Linux's `text_poke`
goes further: it first writes an `int3` over the instruction, so nobody can run it
half-patched.

**2. Threads inside the old code.** A thread that entered the old version before the
patch keeps running it. That memory can't be reused until every such thread has left.
So you wait for a **safepoint**: a point where each thread is known not to be in
generated code, and says so. Here, the worker bumps `epoch` after every call returns.
JVMs, V8 and the kernel's RCU all wait like this, for **quiescence**.

**3. The patching thread's own store buffer.** Until the patch leaves the store buffer,
no other thread sees it, even after "installing". So check the epoch only after an
`mfence` (level 83).

On real hardware there's a fourth: the executing CPU may already have fetched and
decoded the old bytes. Intel's rule for cross-modifying code is that the executing
thread runs a **serializing** instruction (`cpuid`) after it learns of the change
(Linux's `membarrier(SYNC_CORE)` makes every thread do that). The game's CPU doesn't
prefetch instructions, so it can't show that one; the safepoint is the natural place
for it.

The code memory here is writable and executable at once. Patching code in place is why
some JITs can't follow level 53's W^X; others map the same memory twice, once writable
and once executable.

## Gate

1. Find a schedule that breaks the original, and write it as a witness:
   `;! witness schedule = N`.
2. Fix both problems, so that every schedule prints `sum 134850` (and exits with 0).

At most 20 changed lines.
