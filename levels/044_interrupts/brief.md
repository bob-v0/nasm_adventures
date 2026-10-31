# Level 44 — Real-Mode Interrupts

*`int 0x10` and `int 0x13` have been black boxes. They're just far calls through a table,
and the table is yours.*

## Lesson: the interrupt vector table

In real mode, the first 1 KiB of memory, 0000:0000 to 0000:03FF, is the **interrupt
vector table** (IVT): 256 far pointers, 4 bytes each, offset first. Vector n's pointer is
at n × 4:

```
0000:0000   vector 0     offset, segment
0000:0004   vector 1     offset, segment
   ...
0000:0040   vector 0x10  (BIOS video:  0x10 × 4)
0000:004C   vector 0x13  (BIOS disk:   0x13 × 4)
   ...
0000:0200   vector 0x80  (yours:       0x80 × 4)
```

The BIOS fills in the vectors it implements. Nothing stops you from replacing any of
them.

## Lesson: int and iret

`int n` is a call that saves more state:

1. push the flags, then cs, then ip;
2. clear IF and TF (so by default the handler isn't interrupted);
3. jump to the far pointer at n × 4.

`iret` pops ip, cs and the flags back. On entry to the handler, the stack looks like this:

```
   [sp]      ip   ─┐
   [sp + 2]  cs    │ pushed by int
   [sp + 4]  flags ─┘
```

Hardware interrupts (level 42) use exactly the same mechanism, triggered by a device
instead of an instruction. That's why a handler must leave everything as it found it:
the interrupted code doesn't know it was interrupted.

## Lesson: returning a status

BIOS services report errors with the carry flag. A handler can't simply `stc`, because
`iret` restores the caller's flags and the handler's own are lost. So it edits the
**copy on the stack**. After `push bp` / `mov bp, sp`, the stacked flags are at
[bp + 6], and `or byte [bp + 6], 1` sets CF for the caller. (Another trick: `retf 2`, a
far return that drops the stacked flags and keeps the handler's.)

Linux on 32-bit x86 used exactly this mechanism, `int 0x80`, for its system calls. (Arc V
used the newer `syscall` instruction.)

## Gate

Install an `int 0x80` handler with these services, then load the game's test program (2
sectors from LBA 1, as in level 45) at 0000:8000 and jump to 0000:8004. It calls your
services and reports on the serial port.

| ah | service |
|---|---|
| 0 | send the character in al to COM1 |
| 1 | ax = bx + cx |
| 2 | send the NUL-terminated string at ds:si to COM1; return its length in cx |
| anything else | do nothing, return with the carry flag set |

After a service that worked, the carry flag is clear. Every register that isn't a
result, segment registers included, must be as the caller left it.
