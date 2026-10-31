# Level 78 — Bug: False Sharing ◆◆

*Four threads, four counters, no shared data, no locks. Four cores make it slower than
one.*

## Symptoms

Each of four threads counts events in its own counter. Nothing is shared, so this should
scale perfectly: four cores, a quarter of the time. On the game's 4-core CPU it takes
several times longer than it should, and the report says the time goes to "lines from
another core".

## Background: cache coherence

Every core has its own L1 and L2. When two cores cache the same line, the hardware keeps
the copies **coherent** (in agreement) with a protocol: MESI and its relatives. The
essential rule:

- many cores may hold a line for **reading** (Shared);
- to **write** a line, a core must hold the **only** copy (Modified/Exclusive), so every
  other copy is invalidated first.

Moving a line from one core to another costs tens of cycles (about 70 in the game's
model, more across sockets).

## Background: false sharing

Coherence works on whole **64-byte lines**, not on variables. If several cores write
different variables that happen to sit in the same line, each write needs the line
exclusively, so it's pulled from whichever core wrote last, and a moment later another
core pulls it back. The threads share nothing and fight over everything. That's **false
sharing**.

![Counters in one line bounce between cores; counters padded to a line each stay put](false_sharing.svg)

It hides in per-thread statistics, arrays of locks, the fields of a struct written by
different threads, and work queues' head and tail indices. The fix is layout:

- **pad** each independently-written item to its own line (`alignas(64)` in C,
  `CachePadded` in Rust, `@Contended` in Java);
- keep data that's written together, and only that, together.

(True sharing, where several threads really write the same variable, has the same cost
and no layout fix. Then the cure is to share less: for example, per-thread counters,
padded, added up at the end.)

## How the game measures it

Each thread runs on its own core of the CPU model. The cores interleave every few
instructions as if running in parallel, and the run takes as long as the slowest core.
Budget: 4000 cycles.

## Gate

Fix it, changing **1 line**. The total must still be `events 1200`.
