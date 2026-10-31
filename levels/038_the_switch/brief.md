# Level 38 — The Switch

*One bit in a control register, and the CPU is a different machine.*

## Lesson: CR0.PE

**CR0** is the CPU's main control register. Bit 0, **PE** (protection enable), switches
between real and protected mode:

```
cli                     ; nothing may interrupt: there's no protected-mode IDT yet
lgdt [gdt_pointer]      ; level 39's table
mov eax, cr0
or eax, 1
mov cr0, eax            ; protected mode, from the next instruction
jmp 0x08:protected      ; and now a far jump
```

## Lesson: the far jump

Setting PE doesn't change cs: each segment register keeps a hidden, cached copy of its
descriptor, and cs still has the real-mode one. A **far jump** loads cs with a selector,
and the CPU reads entry 1 of the GDT into the cache: now the code segment is the flat
32-bit one, and the next instruction is decoded as 32-bit code. The same goes for the data
segment registers: load each with 0x10.

## Lesson: bits 32

NASM doesn't know what mode the CPU is in. `bits 32` before the protected-mode code tells
it to encode 32-bit instructions (no 66/67 prefixes for 32-bit operands and addresses).
Forget it, and `mov eax, 1` assembles to bytes that 32-bit mode reads differently.

## Lesson: no more BIOS

`int 0x10` and friends are real-mode code reached through the real-mode IVT: in protected
mode, `int` uses the IDT (level 36), which doesn't exist yet. From now on everything is
done by talking to the hardware, which you already can: video memory (level 47) at 0xB8000,
now reachable with a plain 32-bit address, and the serial port (level 46).

## Gate

Switch to protected mode with cs = 0x08 (32-bit) and the data selectors loaded; write
`PROTECTED MODE` on the screen and `Hello from protected mode!` to COM1; halt.
