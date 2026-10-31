# Level 42 — PIT & PIC

*Level 44's handlers ran when the program asked. Hardware interrupts run when a device
asks, between any two instructions of whatever is running.*

## Lesson: the PIC

Devices signal the CPU by raising **IRQ** ("interrupt request") lines. The **8259 PIC**
(programmable interrupt controller) turns a raised line into an interrupt vector. There
are two of them, master and slave, with 8 lines each.

```
timer ──── IRQ 0 ─┐
keyboard ─ IRQ 1 ─┤  master PIC  ──>  vector 8 + n  ──>  CPU (if IF = 1)
   ...    IRQ 2-7 ┘
```

The BIOS sets the master up so that IRQ 0–7 become vectors 8–15. (In protected mode
you'll move them: those vectors are CPU exceptions there.) The CPU takes the interrupt
if IF = 1, exactly as if the running code had executed `int 8`.

Two more things the PIC needs:

- **End of interrupt** (EOI): until the handler writes 0x20 to port 0x20, the PIC won't
  deliver that IRQ (or lower-priority ones) again.
- The **mask**, port 0x21: bit n set = IRQ n ignored.

## Lesson: the PIT

The **8254 PIT** (programmable interval timer) counts down at 1 193 182 Hz (a third of the
original PC's 3.58 MHz colour-TV crystal). Its channel 0 is wired to IRQ 0: each time it
has counted down from its **divisor**, it raises IRQ 0. So interrupts per second =
1 193 182 / divisor.

The BIOS uses the largest divisor, 65536: 18.2 interrupts per second, the "tick" DOS
counted time in. To change it:

```
out 0x43, 0x36      ; command: channel 0, lobyte/hibyte, mode 3, binary
out 0x40, low byte  ; the divisor
out 0x40, high byte
```

## Lesson: sleeping

`hlt` stops the CPU until the next interrupt. With a timer running, that's how an idle
OS waits: the game's test program sleeps between your ticks.

## Gate

1. Program the PIT to interrupt 100 times a second.
2. Handle the interrupt (vector 8) by adding 1 to the dword at 0000:0500, which starts
   at 0. The interrupted code's registers must not change.
3. Load the game's test program (2 sectors from LBA 1) at 0000:8000 and jump to
   0000:8004 with interrupts on.

The test program counts your ticks over a few seconds of the CMOS clock: it expects 100
per second, give or take 2 in all.
