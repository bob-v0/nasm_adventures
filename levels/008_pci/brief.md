# Level 8 — PCI

*Every device you've driven so far sat at an address someone wrote in a manual in 1981.
PCI devices tell you where they are, if you ask the right way.*

## The task

List the **PCI** devices on bus 0, one line per function, then each BAR it uses. Part
of one machine's list (the addresses depend on QEMU's version):

```
00:00.0 8086:29c0 class 06.00.00
00:01.0 1234:1111 class 03.00.00
  bar 0: memory 0xfd000000, 16777216 bytes
  bar 2: memory 0xfebf0000, 4096 bytes
00:02.0 1af4:1005 class 00.ff.00
  bar 0: io 0xc140, 32 bytes
  bar 1: memory 0xfebf1000, 4096 bytes
  bar 4: memory64 0x00000000fe000000, 16384 bytes
```

Each function's line is `bus:device.function vendor:device class class.subclass.prog-if`,
all in hex. Each BAR's line gives its number, its kind (`memory`, `memory64` or `io`),
its address and its size in bytes (in decimal).

The machines are q35 chipsets with different cards plugged in: a network card, a virtio
device with a 64-bit BAR, QEMU's PCI test device. The starter finds **ECAM**'s base for
you, in ACPI's MCFG table (found the way level 9 found the MADT).

## Lesson: configuration space

Every PCI function has a small block of registers that says what it is: its
**configuration space**. It holds a vendor and device id, a class (`02.00` is an
Ethernet controller, `01.06` a SATA controller), and the **BARs** (base address
registers): where the device's own registers live, in memory or in I/O ports.

Functions are addressed by **bus:device.function**: 256 buses, 32 devices per bus, 8
functions per device. A vendor id of 0xFFFF means nothing is there. A device has
functions 1-7 only if its function 0 says it's **multifunction** (bit 7 of the header
type, the byte at +14).

With **ECAM** (the Enhanced Configuration Access Mechanism of PCI Express),
configuration space is ordinary memory: function bus:dev.fn's 4 KiB start at
`ecam + (bus << 20) + (dev << 15) + (fn << 12)`. (Older PCI went through two I/O ports,
0xCF8 and 0xCFC, one dword at a time; level 2 uses them.)

## Lesson: how big is a BAR?

The firmware has already put every BAR somewhere. To find a BAR's *size*, write all
ones to it and read it back. The device keeps the address bits it decodes and holds the
rest at 0, so the read-back value's low zeros give the size. Put the original value
back afterwards, and switch decoding off (the command register at +4) while you probe,
or the device briefly answers at 0xFFFFxxxx.

A **64-bit** memory BAR (type bits 1-2 = 2) takes two slots: the next BAR holds the upper
half of its address, and isn't a BAR of its own.

## Gate

The exact list for every machine the game boots.
