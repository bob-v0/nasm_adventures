# Level 144 — Bug: Assumed Zero ◆◆

*It passed every test its author ran. The tests always started with clean registers;
the real world never does.*

## From now on: poisoned state

Until now every level started your code with registers at 0 (except the inputs). Real
code is called after other code has run, and the registers hold whatever that code left
behind. **From this level on, the tests fill every register the inputs don't set, and
the stack below rsp, with random garbage.** (In Arc IV you'll learn which registers a
caller may rely on.)

Global data in `.data` and `.bss` is still initialized: the OS zeroes `.bss` when the
program loads. Registers and the stack get no such guarantee.

## Symptoms

The routine counts vowels, sums digits and measures the string. With the poisoned
registers, all three results are enormous, and different in every test.

## What to look for

- **Reads before writes:** a register used in an `add` or `inc` before anything
  stored into it.
- **Partial writes:** `mov dl, [mem]` sets only 8 bits; anything that then uses `rdx`
  or `edx` sees the other 56 bits of junk (the bug of level 173, in a new place).

In {{debug}}, look at the registers *before* the first step: that's the junk the code
starts with. Then watch which ones it reads before writing.

## Gate

Make the routine correct regardless of the starting register values, changing at
most **4 lines**.
