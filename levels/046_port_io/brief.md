# Level 46 — Port I/O

*Video memory was one way to reach hardware. The other is older: a separate address
space just for devices.*

## Lesson: I/O ports

Besides memory, x86 has 65 536 **I/O ports**: a separate set of addresses for devices,
reached only with `in` and `out`:

```
out 0x70, al        ; write al to port 0x70 (ports 0-255 can be immediates)
mov dx, 0x3F8
out dx, al          ; higher ports go in dx
in al, dx           ; read a byte from port dx
```

Each device answers at some ports, by a convention as old as the PC:

| ports | device |
|---|---|
| 0x20 / 0x21 | the interrupt controller |
| 0x40–0x43 | the timer |
| 0x60 / 0x64 | the keyboard controller |
| 0x70 / 0x71 | the CMOS clock |
| 0x3F8 (COM1), 0x2F8 (COM2) | the serial ports |
| 0x3C0–0x3DF | VGA |

## Lesson: the 16550 UART

A **UART** sends bytes one bit at a time over a serial line. It's the oldest way to talk
to a computer without a screen: servers' consoles still use it, and QEMU's goes to the
game. COM1's registers:

| port | register |
|---|---|
| 0x3F8 | data: write to send (with DLAB = 1: divisor low byte) |
| 0x3F9 | interrupt enable (with DLAB = 1: divisor high byte) |
| 0x3FB | line control: bits per character, parity, stop bits; bit 7 = DLAB |
| 0x3FD | line status: bit 5 = ready for another byte |

**DLAB** ("divisor latch access bit") switches what 0x3F8 and 0x3F9 mean, so you can set
the speed.

The rule for every device: check the **status** before you write. Sending faster than
the line can carry loses bytes.

## Lesson: the real-time clock

The PC's battery-backed clock lives in the **CMOS** chip. Write a register number to port
0x70, then read the value from port 0x71:

| register | value |
|---|---|
| 0x00 | seconds |
| 0x02 | minutes |
| 0x04 | hours |
| 0x07 | day |
| 0x08 | month |
| 0x09 | year |
| 0x32 | century |

Each is in **BCD** (binary-coded decimal): every 4 bits are one decimal digit. So in
2025 the year byte is 0x25 and the century byte 0x20.

## Gate

Without the BIOS (no `int`; use `in` and `out`), send this line through COM1, then halt:

```
Hello, serial port! Today is YYYY-MM-DD.
```

followed by CR LF, with today's date from the CMOS clock.
