# Level 9 — ACPI

*Your kernel has assumed one CPU and an I/O APIC at 0xFEC00000 since Arc XII.
Real machines tell you what they have. You just have to know where to ask.*

## The task

Find the firmware's **ACPI** tables and report what the **MADT** (Multiple APIC
Description Table) says, one line per entry:

```
cpus: 4
cpu: apic id 0
cpu: apic id 1
cpu: apic id 2
cpu: apic id 3
io apic: id 0, address 0xfec00000, gsi base 0
override: irq 0 -> gsi 2, flags 0x00000000
```

The tests boot different machines: one CPU, four, two sockets of three cores, one with
room for twelve CPUs but only eight present, and a q35 chipset.

## Lesson: following the pointers

![From the RSDP to the MADT](acpi.svg)

1. The **RSDP** (Root System Description Pointer) is the one structure you have to
   search for: the signature `"RSD PTR "` on a 16-byte boundary, in the first KiB of the
   EBDA or in 0xE0000-0xFFFFF. Its first 20 bytes must add up to 0, which is how you know
   you found the real one and not those 8 characters by chance.
2. It points at the **root table**: the RSDT (32-bit addresses), or from revision 2 on the
   XSDT (64-bit).
3. The root table lists every other table. Each starts with a 36-byte header: a 4-letter
   signature and its length. The MADT's signature is `"APIC"`.

## Lesson: what the MADT says

After its header and 8 more bytes come entries, each with a type and a length:

| type | | |
|---|---|---|
| 0 | a processor | its APIC id (+3); flags (+4), bit 0: enabled |
| 1 | an I/O APIC | id (+2), address (+4), the first GSI it handles (+8) |
| 2 | an interrupt override | ISA IRQ (+3) arrives as GSI (+4), with flags (+8) |

Two things kernels get wrong:

- **APIC ids aren't 0, 1, 2, …**: with three cores per socket, ids are 0, 1, 2, 4, 5, 6.
- **Absent CPUs are listed too**, as disabled. Count only the enabled ones.

The overrides matter later. The timer's IRQ 0 is wired to GSI 2, not 0, so a kernel that
routes "IRQ 0" to I/O APIC pin 0 never hears it.

## Gate

The exact report for every machine the game boots.
