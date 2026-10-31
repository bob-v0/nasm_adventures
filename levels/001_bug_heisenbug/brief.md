# Level 1 — Bug: Heisenbug ◆◆◆◆

*It works when you run it the usual way. It works under the debugger. It only fails
in production, on real hardware, with all the cores busy.*

## Symptoms

Objects with **reference counts**: whoever uses an object first takes a reference
(`get`, which adds 1 to its count), and lets it go after (`put`, which takes 1 away).
The `put` that brings the count to 0 frees the object: nobody holds it any more. Every
object starts with one reference, the table's. Every CPU takes and drops references
200000 times, on objects they all share. At the end, the table drops its own reference
to each object, and each must be freed then, exactly once. A freed object is poisoned,
so using one is counted:

```
objects: 64, freed at the end: 64, used after free: 0
```

The game's tests run this two ways. With the CPUs **one at a time** (QEMU's
deterministic mode, which most earlier levels used) it's perfect, every time. With the
CPUs **truly in parallel** (as in levels 5 to 3), it falls apart:

```
objects: 64, freed at the end: 2464, used after free: 6099
```

(The middle number counts every free, so objects freed too early, while in use, show up
there too.)

## Background: a bug that hides

A **heisenbug** changes when you observe it. Single-stepping, printing, a deterministic
emulator: anything that changes the timing can make it vanish. That's why kernels have
tools to *explore schedules* (run the same code under many different interleavings) and
to *record and replay* a failing run. The game's two modes are the simplest version of
that: same kernel, two schedules, two answers.

![Two CPUs increment one count; one increment is lost](race.svg)

Bugs like this come from code that's correct for one CPU and wrong for several. Look for
what every CPU writes, and ask how many steps each write really is.

## Gate

Right on every test, one at a time and in parallel, on 2 to 4 CPUs. At most 4 changed
lines.
