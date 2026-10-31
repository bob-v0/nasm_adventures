# Level 43 — Keyboard

*A key press isn't a character. It's a number from a 1981 microcontroller that says
which switch moved, and which way.*

## Lesson: the keyboard controller

The PC's keyboard talks to the **8042 keyboard controller** (today emulated by the
chipset). You reach it through two ports:

| port | read | write |
|---|---|---|
| 0x64 | status: bit 0 = a byte is waiting in the output buffer | commands to the controller |
| 0x60 | the byte | data to the keyboard |

So: poll port 0x64 until bit 0 is set, then read the byte from port 0x60.

## Lesson: scancodes

What arrives is a **scancode**: the number of the key, not a character. In **set 1**
(what the controller delivers by default), each key sends its code when pressed (a
**make** code), and the code + 0x80 when released (a **break** code). Pressing and
releasing A gives 1E, then 9E.

```
Esc 01   1 02 ... 9 0A  0 0B  - 0C  = 0D  Backspace 0E   Tab 0F
Q 10  W 11  E 12  R 13  T 14  Y 15  U 16  I 17  O 18  P 19  [ 1A  ] 1B   Enter 1C
A 1E  S 1F  D 20  F 21  G 22  H 23  J 24  K 25  L 26  ; 27  ' 28  ` 29   LShift 2A
Z 2C  X 2D  C 2E  V 2F  B 30  N 31  M 32  , 33  . 34  / 35   RShift 36   Space 39
```

Turning scancodes into characters is the program's job: a **keymap** table, plus the
state of the modifier keys (Shift is down between its make and break codes). That's why
keyboard layouts are software.

## Lesson: polling vs interrupts

The keyboard also raises **IRQ 1** for every byte. The BIOS's handler for it (vector 9)
reads port 0x60 and stores characters for `int 0x16`. So if interrupts are on while you
poll, the BIOS gets the byte first.

Either use the BIOS (int 0x16), or take the keyboard over: `cli`, or mask IRQ 1 in the
PIC (level 42). This level takes it over.

## Gate

A line editor that reads the keyboard controller itself (no `int 0x16`):

1. Send `> ` to the serial port (COM1). The game starts typing when it sees it.
2. Build a line from the keys: letters, digits and space are added (with Shift: capital
   letters); Backspace removes the last character, if there is one; at most 70
   characters (more are ignored). Show the line on the screen as it changes.
3. On Enter, send the line and CR LF to COM1, and halt.
