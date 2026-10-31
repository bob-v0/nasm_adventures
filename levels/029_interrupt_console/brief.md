# Level 29 — Interrupt-Driven Console ★

*Two people at two keyboards, one CPU, and a clock that never stops. Nobody waits,
and nothing they type gets lost or mixed up.*

## The console

Your kernel has two inputs:

- the **keyboard** (ISA IRQ 1, scancodes on port 0x60);
- a terminal on the second serial port, **COM2** (port 0x2F8, ISA IRQ 3), sending bytes.

People type on both at the same time. Each source edits its own line:

| | ends the line | deletes the last character | characters |
|---|---|---|---|
| keyboard | Enter (0x1C) | Backspace (0x0E) | letters, digits, space |
| COM2 | carriage return (13); ignore 10 | DEL (0x7F) or BS (8) | bytes 32–126 |

A finished line goes to COM1 (output, as always) with its source:

```
ready
com2: Hello, COM2!
kbd: hello world
kbd: ls
com2: status
```

The two sources' lines may interleave in any order, but each source's lines must come out
whole, unmixed and in the order they were typed. A source that sends the line `bye` is
finished (`kbd: bye` is still printed); when both are, print `bye` and halt with
interrupts off (cli; hlt). Print `ready` when you're listening; the game starts typing then.

Meanwhile the **APIC timer** ticks at 100 Hz, from `ready` to the end: the game compares
`ticks` (a global dword) with the clock.

## Everything in the arc

- the IDT and its gates (level 36), the PIC remapped and masked (34, the helper's there);
- the Local APIC and its calibrated timer (33);
- the I/O APIC: pin 1 and pin 3, each to a vector (32);
- handlers that are short, never reentered, and share data safely with the main loop (31);
- an idle loop that can't miss a wakeup (30).

## The UART's interrupt

COM2 is a 16550 UART like COM1, but for input you also need its interrupt. Its registers,
from the base port 0x2F8:

| port | register | |
|---|---|---|
| +0 | data | read: the byte received |
| +1 | interrupt enable | bit 0: interrupt when a byte arrives |
| +3 | line control | 0x03: 8 bits, no parity, 1 stop bit |
| +4 | modem control | bit 3, OUT2: on real PCs the interrupt line goes through it |
| +5 | line status | bit 0: a byte is waiting |

In the handler, read bytes while bit 0 of the line status is set: there may be more than
one.

## Gate

The game types several conversations, on both inputs at once. Every one must give each
source's lines exactly as typed, `bye` at the end, and the timer at 100 Hz.
