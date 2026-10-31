# Level 2 — Drivers

*Every device so far either sat at a fixed port or was the BIOS's problem. This one you
find on the bus, set up from nothing, and talk to through memory you share with it.*

## The task

The machine has a **virtio-blk** disk (QEMU's paravirtual disk, a PCI device using the
legacy virtio interface). Write its driver:

- **find** it on the PCI bus (vendor 0x1af4, device 0x1001), its I/O ports, and point its
  first **MSI-X** interrupt at this CPU;
- **set up** its request queue;
- **read** sectors: put a request in the queue, tell the device, and **sleep** (`hlt`)
  until its interrupt says done.

The kernel around it (in the starter) reads the disk's tiny filesystem and prints what
the command line asks for:

```
files: 2
  a.txt 6 bytes
  b.txt 7 bytes
== b.txt ==
second
c.txt: no such file
```

The game also checks that every request ended with the device's interrupt.

## Lesson: a virtqueue

The driver and the device share memory: a **virtqueue**.

![A request: three descriptors, offered in the available ring, returned in the used ring](virtqueue.svg)

- **Descriptors**: address, length, flags. A request is a *chain* of three: a header the
  device reads (read, which sector), the buffer it writes, and a status byte it writes.
- The **available ring**: the driver puts a chain's first descriptor there and advances
  the index. Then it writes the queue's number to the device's *notify* register.
- The **used ring**: the device puts finished chains there and advances *its* index. Then
  it interrupts.

## Lesson: MSI-X

PCI interrupts used to be wires (INTx), routed through chipset and I/O APIC tables. With
**MSI-X** a device signals an interrupt by *writing to memory*: to the APIC's address,
with the vector as the data. The device's MSI-X table (in one of its BARs) says what to
write. Fill entry 0, enable MSI-X in its PCI capability, and the interrupt arrives
straight at your IDT.

## Gate

Every test's files, byte for byte, every request finished by an interrupt.
