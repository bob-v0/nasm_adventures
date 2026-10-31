# Level 46 — Port I/O

*Video memory was one way to reach hardware. The other is older: a separate address
space just for devices.*

## Lesson: I/O ports

Besides memory, x86 has 65 536 **I/O ports**, reached only with `in` and `out`:

```
out 0x70, al        ; write al to port 0x70 (ports 0-255 can be immediates)
mov dx, 0x3F8
out dx, al          ; higher ports go in dx
in al, dx           ; read a byte from port dx
```

Each device answers at some ports, by convention as old as the PC: the keyboard
controller at 0x60/0x64, the timer at 0x40-0x43, the interrupt controller at 0x20/0x21,
the serial ports at 0x3F8 (COM1) and 0x2F8, VGA at 0x3C0-0x3DF.

## Lesson: the 16550 UART

A **UART** sends bytes one bit at a time over a serial line, the oldest way to talk to a
computer without a screen (servers' consoles still use it; QEMU's goes to the game).
COM1's registers:

| port | register |
|---|---|
| 0x3F8 | data: write to send (with DLAB = 1: divisor low byte) |
| 0x3F9 | interrupt enable (with DLAB = 1: divisor high byte) |
| 0x3FB | line control: bits per character, parity, stop bits; bit 7 = DLAB |
| 0x3FD | line status: bit 5 = ready for another byte |

The rule for every device: check the **status** before you write. Sending faster than the
line can carry loses bytes.

## Lesson: the real-time clock

The PC's battery-backed clock lives in the **CMOS** chip: write a register number to port
0x70, then read the value from port 0x71. Seconds 0x00, minutes 0x02, hours 0x04, day 0x07,
month 0x08, year 0x09, century 0x32, each in **BCD** (binary-coded decimal): every 4 bits
are one decimal digit, so 2025's year byte is 0x25.

## Gate

Without the BIOS, send `Hello, serial port! Today is YYYY-MM-DD.` and CR LF through COM1,
with the date from the clock.
