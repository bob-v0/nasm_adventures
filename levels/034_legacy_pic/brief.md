# Level 34 — Silencing the PIC

*Every x86-64 kernel takes its interrupts from the APIC. But first it has to deal with the
interrupt controller from 1981 that is still wired into the machine.*

## Lesson: two generations of interrupt controllers

The original PC had one **8259 PIC** (programmable interrupt controller), the AT added a
second one chained to it: 15 IRQ lines, delivered to the CPU as vectors. Since the late
1990s, PCs have the **APIC** instead: a Local APIC in every CPU core (its timer and
inter-processor interrupts, level 33) and an **I/O APIC** that collects the devices' IRQs
(level 32). That's what every modern kernel uses: it scales to many cores and many
devices.

The 8259 pair is still there, emulated by the chipset, and the BIOS leaves it set up for
real mode: IRQ 0-7 as vectors **8-15**. In protected mode those are CPU exceptions (8 is
#DF, 13 is #GP), so a timer tick would look like a double fault. So the first thing a
kernel does with it is make it harmless:

1. **remap** it, so whatever it delivers lands on vectors that mean nothing else
   (0x20-0x2F, right after the 32 exception vectors);
2. **mask** all its lines (ports 0x21 and 0xA1, the interrupt mask registers);
3. handle **spurious** interrupts, which it can deliver even when masked.

## Lesson: remapping

Each PIC takes four **initialization command words**:

| | master (0x20, 0x21) | slave (0xA0, 0xA1) |
|---|---|---|
| ICW1 → 0x20 / 0xA0 | 0x11: initialize, ICW4 follows | 0x11 |
| ICW2 → 0x21 / 0xA1 | 0x20: the first vector | 0x28 |
| ICW3 → 0x21 / 0xA1 | 0x04: a slave on my IRQ 2 | 0x02: I am on IRQ 2 |
| ICW4 → 0x21 / 0xA1 | 0x01: 8086 mode | 0x01 |

## Lesson: spurious interrupts

If an IRQ line goes up and comes down again before the CPU acknowledges it (electrical
noise, a device changing its mind, an IRQ masked at the wrong moment), the PIC has to
deliver *something*, and delivers its lowest-priority vector: **IRQ 7** (or 15 on the
slave). Nothing is in service, so the handler must not send an **EOI**: a non-specific
EOI ends the highest-priority interrupt in service, which would be someone else's.

To tell them apart, ask the PIC: write **0x0B** (OCW3: "read the in-service register")
to port 0x20 and read port 0x20. Bit 7 set: a real IRQ 7. Clear: spurious.

## Gate

Remap both PICs to 0x20 / 0x28, mask every line, and handle vector 0x27 (count spurious
ones in a global `spurious`, no EOI). The game's module, run at 0x400000, checks the masks,
which vector IRQ 0 arrives as, and whether your IRQ 7 handler sends an EOI it shouldn't.
