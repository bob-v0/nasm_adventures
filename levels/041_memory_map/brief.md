# Level 41 — Memory Map & A20

*How much memory does this machine have, and where? Only the BIOS knows. And one of
the oldest compatibility hacks in the PC decides whether you can reach it.*

## Lesson: the memory map

Physical addresses aren't all RAM: the first megabyte has the BIOS's data, the EBDA,
video memory at A0000-BFFFF and ROMs above, and higher up there are ACPI tables, PCI
devices and holes. An operating system asks the BIOS for the **E820 map**:

```
mov eax, 0xE820
mov edx, 'PAMS'       ; the signature, 0x534D4150 ('SMAP' in the right byte order)
mov ecx, 24           ; the buffer's size
mov di, buffer        ; es:di
xor ebx, ebx          ; 0: the first entry
int 0x15              ; buffer = base (8 bytes), length (8), type (4); ebx = next
```

Call it again with the returned ebx until it returns ebx = 0. Type 1 is usable RAM,
2 reserved, 3 ACPI tables (reclaimable), 4 ACPI non-volatile, 5 bad memory. Linux prints
this map at boot: `dmesg | grep e820`.

## Lesson: A20

The 8086 had 20 address lines: FFFF:0010 = 0x100000 wrapped around to 0x00000, and some
DOS programs relied on it. The 286 had 24 lines, so IBM added a gate on line 20, **A20**,
controlled through the *keyboard controller*, off by default so that old programs kept
wrapping. Every PC since starts with this switch, and every boot loader turns it on before
using memory above 1 MiB.

Ways to turn it on: the "fast A20" bit 1 of **port 0x92**; the keyboard controller's
output port (command 0xD1 to port 0x64); or the BIOS (int 15h, ax = 0x2401). None is
guaranteed on every machine, so careful code tries them in turn and **tests** after
each: write a byte at 0000:0500, a different one at FFFF:0510; if the first changed, the
second write wrapped.

## Gate

Print the BIOS's whole E820 map in the starter's format, turn A20 on and verify it, and
halt. Tested on machines with different amounts of memory.
