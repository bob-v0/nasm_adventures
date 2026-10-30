# Level 90 — Atomics

*Two threads add 1 to a counter at the same moment. The counter goes up by 1.*

## Lesson: read-modify-write is three steps

`add [counter], 1` looks like one step. Inside the CPU it's three: **read** the value,
**add**, **write** it back. Two cores doing that at the same time can both read 5, both
write 6. One addition vanishes: a **lost update**. On a single core the same happens when
a thread switch lands between a `mov` from memory and the `mov` back.

## Lesson: the lock prefix

x86 gives a few instructions an **atomic** form: nothing can happen to the memory
location between their read and their write. The core takes exclusive ownership of the
cache line for the whole instruction, so no other core can touch it in between.

| instruction | does, atomically |
|---|---|
| `lock add/sub/inc/dec/and/or/xor [m], r` | the operation (no result back) |
| `lock xadd [m], r` | `tmp = [m]; [m] += r; r = tmp`: **fetch-and-add**, returns the old value |
| `xchg [m], r` | swaps; with a memory operand it's **always** locked |
| `lock cmpxchg [m], r` | if `[m] == rax`: `[m] = r`, ZF = 1; else `rax = [m]`, ZF = 0 |

`lock` works only with these read-modify-write instructions and a memory destination.
Locked instructions also act as a full **fence** (more in level 83). They're not free:
a contended cache line bounces between cores, at tens to hundreds of cycles per
operation.

## Lesson: compare-and-swap

Anything without its own instruction (a maximum, a linked-list push, a state machine)
uses **CAS** in a loop:

```
read the old value
compute the new value from it
lock cmpxchg: store it only if the location still holds the old value
if someone got there first: cmpxchg gave you their value, try again
```

Almost every lock-free algorithm (levels 77–72) is built from this loop.

## Gate

Write `atomic_fetch_add`, `atomic_swap` and `atomic_max` (unsigned). The game's harness
runs 4 threads that use them at the same time and checks that every ticket from
`atomic_fetch_add` is handed out exactly once, that the maximum is right, and that every
value swapped in comes back out exactly once. It runs them under many schedules, with
store buffers (from now on, the game's threads run on a model of real x86 memory: more on
that in level 83).
