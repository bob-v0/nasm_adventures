/* The game's linker script for multiboot kernels (Arcs XII-XIV): loaded at 1 MiB,
   the multiboot header first (it must be in the first 8 KiB of the file). */
ENTRY(_start)
SECTIONS {
    . = 0x100000;
    .multiboot : { *(.multiboot) }
    .text : { *(.text) }
    .rodata : { *(.rodata) }
    .data : { *(.data) }
    .bss : { *(.bss) *(COMMON) }
    kernel_end = .;
}
