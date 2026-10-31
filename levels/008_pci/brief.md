# Level 8 — PCI

*Every device you've driven so far sat at an address someone wrote in a manual in 1981.
PCI devices tell you where they are, if you ask the right way.*

## The task

List the **PCI** devices on bus 0, one line per function, then each BAR it uses:

```
00:02.0 8086:100e class 02.00.00
  bar 0: memory 0xfeb80000, 131072 bytes
  bar 1: io 0xc100, 64 bytes
00:03.0 1af4:1005 class 00.ff.00
  bar 4: memory64 0x00000000fe000000, 16384 bytes
```

The machines are q35 chipsets with different cards plugged in: a network card, a virtio
device with a 64-bit BAR, QEMU's PCI test device. The starter finds **ECAM**'s base for
you, in ACPI's MCFG table.

## Lesson: configuration space

Every PCI function has a small block of registers that says what it is: **configuration
space**. It holds a vendor and device id, a class (`02.00` is an Ethernet controller,
`01.06` a SATA controller), and the **BARs** (base address registers): where the device's
own registers live, in memory or in I/O ports.

Functions are addressed by **bus:device.function**: 256 buses, 32 devices per bus, 8
functions per device. A device has functions 1-7 only if its function 0 says it's
**multifunction** (bit 7 of the header type).

With **ECAM** (PCI Express), configuration space is ordinary memory: function
bus:dev.fn's 4 KiB start at `ecam + (bus << 20) + (dev << 15) + (fn << 12)`. (Older PCI went
through two I/O ports, 0xCF8 and 0xCFC, one dword at a time.)

## Lesson: how big is a BAR?

The firmware has already put every BAR somewhere. To find a BAR's *size*, write all
ones to it and read back. The device keeps the bits it decodes and holds the rest at 0,
so the read-back value's low zeros give the size. Put the original value back
afterwards, and switch decoding off while you probe, or the device briefly answers at
0xFFFFxxxx.

A **64-bit** memory BAR (type bits = 2) takes two slots: the next BAR holds its address's
upper half.

## Gate

The exact list for every machine the game boots.
