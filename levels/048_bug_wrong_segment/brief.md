# Level 48 — Bug: Wrong Segment ◆◆

*It works in QEMU, and on the developer's laptop. It doesn't work on yours.*

## Symptoms

A tiny boot menu: a title and two entries, printed with the BIOS. On some machines the
screen stays empty, or fills with garbage, or the machine hangs before the menu.

## Background: what the BIOS promises

The BIOS loads the boot sector at physical address **0x7C00** and jumps to it with **dl**
= the boot drive. That's all it promises. In particular:

- **cs:ip** can be `0000:7C00` (most BIOSes, SeaBIOS) or `07C0:0000` (some older and
  embedded BIOSes). It's the same physical byte, but ip counts from 0x7C00 in the first
  and from 0 in the second.
- **ds, es, ss, sp** can hold anything: whatever the BIOS used last.

Code assembled with `org 0x7C00` assumes offsets that start at 0x7C00, so it needs
segment registers of 0.

Relative jumps and calls (`jmp label`, `call label`) work either way: they only add a
distance to ip. But anything that turns a label into an absolute offset needs the right
segment: data accesses, a jump or call *through* a pointer, a `ret` to a pushed address.

## Background: the usual fix

Real boot sectors start by setting all of it themselves:

```
    jmp 0:.go           ; far jump: cs = 0, ip = .go's offset (org 0x7C00)
.go:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax          ; ss and sp together, with interrupts off:
    mov sp, 0x7C00      ; an interrupt between them would use a half-set stack
    sti
```

(The other consistent choice: `org 0` and segments of 0x07C0.)

## Gate

1. Find a BIOS the original fails on, and write it as a witness:
   `;! witness bios = "odd"` (the choices are `"seabios"` and `"odd"`).
2. Make the menu appear, exactly, on both.

At most 12 changed lines.
