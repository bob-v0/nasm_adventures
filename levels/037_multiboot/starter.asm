; Level 37 — Multiboot
;
; A kernel, loaded by a multiboot loader (QEMU's: `qemu-system-i386 -kernel`). It
; starts in 32-bit protected mode, at _start. Send to COM1, each line ending in CR LF:
;   booted by a multiboot loader          (if eax = 0x2BADB002; otherwise say so)
;   command line: <the command line>
;   memory: <mem_lower> KiB low, <mem_upper> KiB high
;   modules: <how many>
; and then the bytes of each module, one after the other. Halt.

bits 32

section .multiboot
align 4
    ; TODO: the multiboot header

section .text
global _start
_start:
    ; TODO
    cli
    hlt
