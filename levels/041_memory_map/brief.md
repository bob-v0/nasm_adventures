# Level 41 — Memory Map & A20

*How much memory does this machine have, and where? Only the BIOS knows. And one of
the oldest compatibility hacks in the PC decides whether you can reach it.*

## Lesson: the memory map

Physical addresses aren't all RAM. The first megabyte holds the BIOS's data, the EBDA
(extended BIOS data area), video memory at A0000–BFFFF and ROMs above it (level 50's
map). Higher up there are ACPI tables, PCI devices and holes. So an operating system
asks the BIOS for the **E820 map**, one entry per call:

```
mov eax, 0xE820
mov edx, 'PAMS'       ; the signature, 0x534D4150 ('SMAP' in the right byte order)
mov ecx, 24           ; the buffer's size
mov di, buffer        ; es:di
xor ebx, ebx          ; 0: the first entry
int 0x15              ; buffer = base (8 bytes), length (8), type (4); ebx = next
```

Call it again with the returned ebx, until it returns ebx = 0: that was the last entry.

| type | meaning |
|---|---|
| 1 | usable RAM |
| 2 | reserved |
| 3 | ACPI tables (reclaimable) |
| 4 | ACPI non-volatile |
| 5 | bad memory |

Linux prints this map at boot: `dmesg | grep e820`.

Real mode can use the 32-bit registers and operations (eax, ebx, ...); only addresses
are 16-bit.

## Lesson: A20

The 8086 had 20 address lines, so FFFF:0010 = 0x100000 wrapped around to 0x00000, and
some DOS programs relied on it. The 286 had 24 lines. To keep the old programs working,
IBM added a gate on address line 20, **A20**, controlled through the *keyboard
controller* and off by default. Every PC since starts with this switch, and every boot
loader turns it on before using memory above 1 MiB.

With A20 off, bit 20 of every address is forced to 0:

```
FFFF:0510  ->  FFFF0 + 0510 = 100500
A20 on:        100500     (just above 1 MiB)
A20 off:       000500     (bit 20 dropped: wraps to the bottom)
```

There are several ways to turn it on: the "fast A20" bit 1 of **port 0x92**; the keyboard
controller's output port (command 0xD1 to port 0x64); or the BIOS (int 15h, ax =
0x2401). None is guaranteed on every machine, so careful code tries them in turn and
**tests** after each: write a byte at 0000:0500 and a different one at FFFF:0510. If the
first one changed, the second write wrapped, and A20 is still off.

## Gate

This BIOS leaves A20 off. Then:

1. Ask the BIOS for the memory map (int 15h, eax = 0xE820) and send every entry to COM1
   as one line (the format is below).
2. Turn A20 on, check that memory above 1 MiB no longer wraps around to 0, and send
   `A20 is on` and CR LF.
3. Halt.

Each map line is the base and the length as 16 lowercase hex digits each, then the type
as one digit, separated by single spaces, ending with CR LF:

```
0000000000000000 000000000009fc00 1
```

The serial output must match the BIOS's map line for line. It's tested on machines
with different amounts of memory, and A20 must be on when you halt.
