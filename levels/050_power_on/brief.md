# Level 50 — Power On

*Arc XI: no operating system any more. Under you there is nothing but the machine, and
it starts from nothing.*

## Lesson: the first instruction

When an x86 CPU is switched on (or reset), it starts in **real mode**: the 16-bit mode
of the 1978 8086. It runs its first instruction at physical address **FFFF0**, the
**reset vector**. That's 16 bytes below the end of the first megabyte, in the BIOS's
ROM: just room for a far jump into the rest of the BIOS.

The **BIOS** (here SeaBIOS, QEMU's) then tests and sets up the hardware, and builds
tables the operating system will ask for. Then it looks for a disk to boot:

1. it reads the disk's first sector, 512 bytes, to address **0x7C00**;
2. it checks that the sector's last two bytes are **55 AA**;
3. it jumps to 0x7C00 with **dl** = the drive number it booted from (0x80: the first hard
   disk).

That sector, the **boot sector** (the MBR on a hard disk), is yours.

![The first megabyte of memory in real mode](memory_map.svg)

## Lesson: a boot sector in NASM

```
bits 16                         ; 16-bit code: the CPU is in real mode
org 0x7C00                      ; NASM: the code will sit at 0x7C00
start:
    ...
    cli                         ; no interrupts...
    hlt                         ; ...so nothing wakes the CPU: it stops for good
times 510 - ($ - $$) db 0       ; zeros up to byte 510 ($ = here, $$ = the start)
dw 0xAA55                       ; the boot signature: bytes 55 AA
```

No ELF, no linker: `nasm -f bin` writes exactly these bytes.

`org` doesn't move the code anywhere. It tells NASM what address to give the labels.
Leave it out and `magic` is 0x0E instead of 0x7C0E, and every memory access through a
label misses.

In real mode the registers are 16 bits (ax, bx, ..., sp, ip; the 32-bit ones still
exist). A memory address is a **segment** register times 16 plus an offset: `[bx]`
means ds × 16 + bx, and `[es:0xFFF0]` means es × 16 + 0xFFF0. Level 49 is about that;
here it's enough that es = 0xF000 reaches the reset vector at F000:FFF0 = FFFF0.

## Lesson: running and debugging

The game boots your sector in QEMU, a whole emulated PC, and reads the registers when
the CPU halts. To look inside:

- {{boot_debug}} starts QEMU stopped at the reset vector, with gdb attached:
  `x/5xb 0xffff0`, `si`, `info registers`, `break *0x7c00`, `continue`;
- `qemu-system-x86_64 -drive format=raw,file=solution.img -display curses` in
  {{terminal}} boots the image so you can watch (after {{test}}, which writes
  `solution.img`).

## Gate

Halt (`cli`, then `hlt`) with these registers:

- ax = 0xB007, read from the word at the label `magic`;
- bx = the address of `magic`;
- dl = the boot drive, as the BIOS left it;
- si:di = the segment:offset that the reset vector's far jump goes to.
