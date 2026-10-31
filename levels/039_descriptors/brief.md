# Level 39 — Descriptors

*Arc XII: protected mode, the mode every 32-bit operating system ran in. It begins with a
table that tells the CPU what a segment is.*

## Lesson: segments become descriptors

In real mode a segment register holds a number that is multiplied by 16. In **protected
mode** it holds a **selector**, an index into a table of **segment descriptors**, and the
descriptor says where the segment starts (its **base**), how long it is (its **limit**),
and what may be done with it: execute, read, write, at which privilege level.

The table is the **GDT**, the global descriptor table, wherever you put it in memory. The
CPU finds it through the **GDTR** register, loaded with `lgdt [pointer]` from 6 bytes:

```
gdt_pointer:
    dw gdt_end - gdt - 1    ; limit: the table's size minus one
    dd gdt                  ; base: its linear address
```

## Lesson: a descriptor

Eight bytes, with the fields scattered for compatibility with the 286:

```
 byte:   0-1          2-3         4          5          6                   7
        limit 0-15   base 0-15   base 16-23  access    flags | limit 16-19  base 24-31

 access: P DPL S type        P = present, DPL = privilege 0-3, S = 1 for code/data
         type (code): 1 C R A   execute; R = readable        1010 = 0xA
         type (data): 0 E W A   W = writable                 0010 = 0x2
 flags:  G D L 0             G = limit counts 4 KiB pages, D = 32-bit, L = 64-bit
```

Entry 0 must be the **null descriptor** (all zeros): selector 0 means "no segment".

## Lesson: the flat model

Every 32-bit OS (Linux, Windows, the BSDs) uses segments as little as possible: one code
and one data segment, both with base 0 and a limit of 4 GiB (0xFFFFF in 4 KiB units). Then
an address is just an address, and protection comes from paging (level 31) instead.

A **selector** is the entry's offset: entry 1 is 0x08, entry 2 is 0x10. Its low 3 bits
are flags (bit 2: the LDT instead of the GDT; bits 0-1: the requested privilege, RPL),
which is why entries are 8 bytes apart.

## Gate

A GDT with the null descriptor, a flat 32-bit ring-0 code segment (0x08) and a flat data
segment (0x10), loaded with `lgdt`. The game reads GDTR and checks each field.
