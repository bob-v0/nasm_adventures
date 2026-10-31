# Level 2 — Drivers

*Every device so far either sat at a fixed port or was the BIOS's problem. This one you
find on the bus, set up from nothing, and talk to through memory you share with it.*

## The task

The machine has a **virtio-blk** disk: QEMU's *paravirtual* disk, a device designed
for virtual machines rather than copied from real hardware. It sits on the PCI bus and
here uses virtio's older ("legacy") interface, a block of registers in I/O ports. Write
its driver (`find_disk`, `virtio_init`, `read_sectors`, `disk_irq`):

- **find** it on PCI bus 0 (vendor 0x1af4, device 0x1001) and its I/O ports (BAR 0),
  and point its first **MSI-X** interrupt at this CPU;
- **set up** its request queue;
- **read** sectors: put a request in the queue, tell the device, and **sleep** (`hlt`)
  until its interrupt says done.

This level reads configuration space through the old ports 0xCF8 and 0xCFC (level 8's
aside): the starter's `config_read` and `config_write` do it for you.

The kernel around it (in the starter) reads the disk's tiny filesystem and prints what
the command line asks for. With the command line `b.txt c.txt`:

```
files: 2
  a.txt 6 bytes
  b.txt 7 bytes
== b.txt ==
second
c.txt: no such file
```

The game also checks that every request ended with the device's interrupt: your
`requests` and `completions` counters must agree.

## Lesson: a virtqueue

The driver and the device share memory: a **virtqueue**.

![A request: three descriptors, offered in the available ring, returned in the used ring](virtqueue.svg)

- **Descriptors**: address, length, flags, and the next descriptor's number. A request
  is a *chain* of three: a header the device reads (read, which sector), the buffer it
  writes, and a status byte it writes (0: done).
- The **available ring**: the driver puts a chain's first descriptor there and advances
  the ring's index. Then it writes the queue's number to the device's *notify* register.
- The **used ring**: the device puts finished chains there and advances *its* index. Then
  it interrupts.

With the legacy interface, the driver tells the device where all this is with one
number: the page the queue starts on. The layout follows from the queue's size, which
the device chooses.

## Lesson: MSI-X

PCI interrupts used to be wires (INTx), routed through chipset and I/O APIC tables. With
**MSI-X** (message-signalled interrupts, extended) a device signals an interrupt by
*writing to memory*: to the local APIC's address, with the vector as the data. The
device's MSI-X table (in one of its memory BARs) says what to write.

You find MSI-X in the device's **capability list**: a chain of small records in
configuration space, starting from the byte at 0x34, each with an id and the next one's
offset. MSI-X's id is 0x11. Fill table entry 0, tell the device that the queue's
interrupts use entry 0, enable MSI-X in the capability, and the interrupt arrives
straight at your IDT.

## Gate

Every test's files, byte for byte, every request finished by an interrupt.
