# Level 44 — Real-Mode Interrupts

*`int 0x10` and `int 0x13` have been black boxes. They're just far calls through a table,
and the table is yours.*

## Lesson: the interrupt vector table

In real mode, the first 1 KiB of memory, 0000:0000 to 0000:03FF, is the **interrupt
vector table** (IVT): 256 far pointers, 4 bytes each, offset first. Vector n's pointer is
at n × 4. The BIOS fills in the ones it implements; nothing stops you from replacing any
of them.

## Lesson: int and iret

`int n` is a call with more state:

1. push the flags, then cs, then ip;
2. clear IF and TF (so the handler isn't interrupted by default);
3. jump to the far pointer at n × 4.

`iret` pops ip, cs and the flags back. Hardware interrupts (level 42) use exactly the
same mechanism, triggered by a device instead of an instruction, which is why a handler
must leave everything as it found it: the interrupted code doesn't know it was
interrupted.

```
   [sp]      ip   ─┐
   [sp + 2]  cs    │ pushed by int
   [sp + 4]  flags ─┘
```

## Lesson: returning a status

BIOS services report errors with the carry flag. A handler can't simply `stc`: `iret`
restores the caller's flags, its own are lost. So it edits the **copy on the stack**:
with `push bp` / `mov bp, sp`, the stacked flags are at [bp + 6], and
`or byte [bp + 6], 1` sets CF for the caller. (Another trick: `retf 2`, a far return that
skips the flags, keeping the handler's.)

Linux on 32-bit x86 used exactly this mechanism, `int 0x80`, for its system calls (Arc V
used the newer `syscall` instruction).

## Gate

An `int 0x80` handler with the three services in the starter, tested by the game's
program, with every register preserved and the carry flag right.
