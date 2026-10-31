# Level 9 — ACPI

*Your kernel has assumed one CPU and an I/O APIC at 0xFEC00000 since Arc XII.
Real machines tell you what they have. You just have to know where to ask.*

## The task

**ACPI** (the Advanced Configuration and Power Interface) is a set of tables the
firmware leaves in memory to describe the machine. Find them, and report what the
**MADT** (Multiple APIC Description Table) says, on the serial port, one line per entry
in the order the table lists them. On four CPUs:

```
cpus: 4
cpu: apic id 0
cpu: apic id 1
cpu: apic id 2
cpu: apic id 3
io apic: id 0, address 0xfec00000, gsi base 0
override: irq 0 -> gsi 2, flags 0x00000000
override: irq 5 -> gsi 5, flags 0x0000000d
override: irq 9 -> gsi 9, flags 0x0000000d
override: irq 10 -> gsi 10, flags 0x0000000d
override: irq 11 -> gsi 11, flags 0x0000000d
```

The first line counts the enabled CPUs. Entries of other types print nothing.

The tests boot different machines: one CPU, four, two sockets of three cores, one with
room for twelve CPUs but only eight present, and a q35 chipset with two CPUs. Paging is
off, so every physical address can be used as it is.

## Lesson: following the pointers

![From the RSDP to the MADT](acpi.svg)

1. The **RSDP** (Root System Description Pointer) is the one structure you have to
   search for: the 8 characters `"RSD PTR "` on a 16-byte boundary, either in the first
   KiB of the EBDA (the extended BIOS data area; its segment is the word at 0x40E) or in
   0xE0000-0xFFFFF. Its first 20 bytes must add up to 0 (mod 256): that's how you know
   you found the real one, not those 8 characters by chance.
2. It points at the **root table**: the RSDT (32-bit addresses, at +16), or, if the
   RSDP's revision (byte 15) is 2 or more, the XSDT (64-bit addresses, at +24).
3. The root table lists every other table. Each table starts with a 36-byte header: a
   4-letter signature, then its length (a dword at +4). The MADT's signature is `"APIC"`.

## Lesson: what the MADT says

After its header come 8 more bytes (the local APIC's address and some flags), then the
entries, each starting with a type byte and a length byte:

| type | what | fields (offset in the entry) |
|---|---|---|
| 0 | a processor | its APIC id (+3); flags (+4), bit 0: enabled |
| 1 | an I/O APIC | id (+2), address (+4), the first GSI it handles (+8) |
| 2 | an interrupt override | ISA IRQ (+3) arrives as GSI (+4), with flags (a word, +8) |

A **GSI** (global system interrupt) is an I/O APIC input, numbered across all the
machine's I/O APICs.

Two things kernels get wrong:

- **APIC ids aren't 0, 1, 2, …**: with three cores per socket, ids are 0, 1, 2, 4, 5, 6.
- **Absent CPUs are listed too**, as disabled. Count only the enabled ones.

The overrides matter later. The timer's IRQ 0 is wired to GSI 2, not 0, so a kernel that
routes "IRQ 0" to I/O APIC input 0 never hears it.

## Gate

The exact report for every machine the game boots.
