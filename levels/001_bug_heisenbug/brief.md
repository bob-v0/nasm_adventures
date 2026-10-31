# Level 1 — Bug: Heisenbug ◆◆◆◆

*It works when you run it the usual way. It works under the debugger. It only fails
in production, on real hardware, with all the cores busy.*

## Symptoms

Objects with **reference counts**: whoever uses an object first takes a reference
(`get`), and lets it go after (`put`). The last `put` frees it. Every CPU does this
200000 times, on objects they all share. At the end, the table drops its own reference
to each object, and each must be freed then, exactly once:

```
objects: 64, freed at the end: 64, used after free: 0
```

The game's tests run this two ways. With the CPUs **one at a time** (QEMU's usual,
deterministic mode, the one every earlier level used) it's perfect, every time. With the
CPUs **truly in parallel**, it falls apart:

```
objects: 64, freed at the end: 2464, used after free: 6099
```

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

Right on every test, one at a time and in parallel, 2 to 4 CPUs. At most 4 changed lines.
