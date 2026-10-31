# Level 37 — Multiboot

*Every kernel used to write its own boot sector and its own protected-mode switch.
Multiboot ended that: a standard boot loader (GRUB) does it, and your kernel starts in
protected mode with a description of the machine.*

## Lesson: the contract

The **multiboot** specification (1995) is a contract between boot loaders and kernels.
The kernel puts a **header** somewhere in its first 8 KiB:

```
section .multiboot
align 4
    dd 0x1BADB002                   ; magic
    dd FLAGS                        ; what it asks for
    dd -(0x1BADB002 + FLAGS)        ; checksum: the three dwords add up to 0
```

In FLAGS, bit 0 asks for page-aligned modules and bit 1 for memory information.

The loader (GRUB, or QEMU's `-kernel`) finds the header and loads the kernel (an ELF
file) where it was linked, here 1 MiB. It loads any **modules** (other files: an initial
ramdisk, programs) after it. Then it jumps to the kernel's entry point with:

- 32-bit protected mode, flat 4 GiB code and data segments, paging off, interrupts off;
- **eax = 0x2BADB002**: proof that a multiboot loader did it;
- **ebx = the address of the multiboot information structure**.

There's no stack: set esp first. (The GDT the loader used may be anywhere in memory. A
real kernel loads its own, as in level 39, before trusting the segment registers again.)

## Lesson: the information structure

ebx points at this structure. The flags field at offset 0 says which of the others are
valid:

| offset | field | valid if flags bit |
|---|---|---|
| 0 | flags: which fields are valid | |
| 4 | mem_lower: KiB of memory below 1 MiB | 0 |
| 8 | mem_upper: KiB above 1 MiB | 0 |
| 16 | cmdline: address of the command line, a C string | 2 |
| 20 | mods_count | 3 |
| 24 | mods_addr: an array of { mod_start, mod_end, string, reserved } | 3 |
| 44 | mmap_length, mmap_addr: the memory map (level 41's E820, as entries) | 6 |

Each module entry is 16 bytes: the module's bytes run from mod_start up to (not
including) mod_end.

## Lesson: building a kernel

From this level on your code is linked, not flat. NASM writes a 32-bit ELF object
(`-f elf32`), and the game's linker script places `.multiboot` first and everything at
1 MiB. So your labels are real addresses, and `section .bss` costs no space in the file.

Try it yourself in {{terminal}} after {{test}}:
`qemu-system-i386 -kernel solution.elf -append "hello" -serial stdio -display none`.

## Gate

Send these lines to COM1, each ending in CR LF:

```
booted by a multiboot loader
command line: <the command line>
memory: <mem_lower> KiB low, <mem_upper> KiB high
modules: <how many>
```

(The first line only if eax = 0x2BADB002; otherwise say so.) Then send the bytes of
each module, one after the other, and halt. The command line is the loader's string as
it is: QEMU's starts with the kernel's name, `kernel.elf`.

Tested with different command lines, memory sizes and modules.
