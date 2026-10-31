# Level 33 — Local APIC

*Every core has its own interrupt controller, with its own timer. It's what drives the
scheduler of every x86-64 operating system you have used.*

## Lesson: the Local APIC

Each CPU core has a **Local APIC** (advanced programmable interrupt controller). It
receives interrupts (from devices through the I/O APIC, level 32, from other cores, from
its own timer), decides which to deliver to its core, and is told when one is done (EOI).

Its registers aren't I/O ports: they are **memory-mapped**, a 4 KiB page normally at
physical **0xFEE00000**. Reading or writing those addresses talks to the APIC, not to RAM.
The base address is in the **IA32_APIC_BASE** model-specific register (MSR 0x1B, read with
`rdmsr`: ecx = the MSR number, the value in edx:eax).

| offset | register |
|---|---|
| 0x0B0 | EOI: write anything to end the current interrupt |
| 0x0F0 | spurious-interrupt vector: bit 8 enables the APIC, low byte = the vector for spurious interrupts |
| 0x320 | LVT timer: the timer's vector, bit 16 masked, bit 17 periodic |
| 0x380 | initial count |
| 0x390 | current count (read only) |
| 0x3E0 | divide configuration: 3 = ÷16 |

## Lesson: the APIC timer

The timer counts down from the initial count at the bus clock divided by the divide
setting; at 0 it interrupts and, in periodic mode, starts again. Its speed differs from
machine to machine, so a kernel **calibrates** it against a clock it knows: the PIT
(level 42's 1.193182 MHz). PIT channel 2 is convenient for that: its gate and output are
bits 0 and 5 of port 0x61, so a 10 ms one-shot can be polled without any interrupt.

```
APIC timer: count down from 0xFFFFFFFF
PIT channel 2: count 11932 (10 ms), wait for its output
APIC counts per 10 ms = 0xFFFFFFFF − current count
periodic, initial count = that  →  100 interrupts a second
```

## Gate

Enable the Local APIC, calibrate its timer and run it at 100 Hz on vector 0x40, counting
in `ticks` (global), with the legacy PIC masked. Then call the game's module at 0x400000
with eax = the address of `ticks`.
