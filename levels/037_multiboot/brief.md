# Level 37 — Multiboot

*Every kernel used to write its own boot sector and its own protected-mode switch.
Multiboot ended that: a standard boot loader (GRUB) does it, and your kernel starts in
protected mode with a description of the machine.*

## Lesson: the contract

The **multiboot** specification (1995) is a contract between boot loaders and kernels.
The kernel puts a **header** in its first 8 KiB:

```
section .multiboot
align 4
    dd 0x1BADB002                   ; magic
    dd FLAGS                        ; what it asks for
    dd -(0x1BADB002 + FLAGS)        ; checksum: the three dwords add up to 0
```

The loader (GRUB, or QEMU's `-kernel`) finds it, loads the kernel (an ELF file) where it
was linked (here 1 MiB), loads any **modules** (other files: an initial ramdisk, programs)
after it, and jumps to the entry point with:

- 32-bit protected mode, flat 4 GiB code and data segments, paging off, interrupts off;
- **eax = 0x2BADB002** (proof that a multiboot loader did it);
- **ebx = the address of the multiboot information structure**.

No stack: set esp first. (The GDT the loader used may be anywhere: a real kernel loads its
own, as level 39, before trusting the segment registers again.)

## Lesson: the information structure

| offset | field | with flags bit |
|---|---|---|
| 0 | flags: which fields are valid | |
| 4 | mem_lower: KiB of memory below 1 MiB | 0 |
| 8 | mem_upper: KiB above 1 MiB | 0 |
| 16 | cmdline: address of the command line, a C string | 2 |
| 20 | mods_count | 3 |
| 24 | mods_addr: an array of { mod_start, mod_end, string, reserved } | 3 |
| 44 | mmap_length, mmap_addr: the memory map (level 41's E820, as entries) | 6 |

## Lesson: building a kernel

From this level on your code is linked, not flat: NASM writes a 32-bit ELF object
(`-f elf32`), and the game's linker script places `.multiboot` first and everything at
1 MiB. Your labels are real addresses; `section .bss` costs no space in the file.

Try it yourself in {{terminal}} after {{test}}:
`qemu-system-i386 -kernel solution.elf -append "hello" -serial stdio -display none`.

## Gate

Report the magic, the command line, the memory sizes and the modules (their contents) on
the serial port. Tested with different command lines, memory sizes and modules.
