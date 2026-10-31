# Level 42 — PIT & PIC

*Level 44's handlers ran when the program asked. Hardware interrupts run when a device
asks, between any two instructions of whatever is running.*

## Lesson: the PIC

Devices raise **IRQ** lines. The **8259 PIC** (programmable interrupt controller; two of
them, master and slave, 8 lines each) turns a raised line into an interrupt vector for
the CPU: the BIOS sets the master up so that IRQ 0-7 are vectors 8-15 (in protected mode
you'll move them: those vectors are CPU exceptions there). The CPU takes it if IF = 1,
exactly like `int 8`.

The PIC then waits for an **end of interrupt** (EOI): until the handler writes 0x20 to
port 0x20, it won't deliver that IRQ (or lower-priority ones) again. Port 0x21 is the
**mask**: bit n set = IRQ n ignored.

## Lesson: the PIT

The **8254 PIT** (programmable interval timer) counts down at 1 193 182 Hz (a third of the
original PC's 3.58 MHz colour-TV crystal). Channel 0 is wired to IRQ 0: each time it
counts down from its **divisor** it raises IRQ 0. The BIOS uses the largest divisor,
65536: 18.2 interrupts per second, the "tick" DOS counted time in.

```
out 0x43, 0x36      ; command: channel 0, lobyte/hibyte, mode 3, binary
out 0x40, low byte  ; the divisor
out 0x40, high byte
```

## Lesson: sleeping

`hlt` stops the CPU until the next interrupt. With a timer running that's how an idle
OS waits: the game's test program sleeps between your ticks.

## Gate

Interrupt 100 times a second, count the interrupts at 0000:0500, and hand over to the
game's test program, which checks the rate against the CMOS clock.
