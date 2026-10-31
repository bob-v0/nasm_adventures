; Level 36 — Exceptions
;
; Load your own GDT (level 39's), then an IDT with a handler for each of the 32
; exception vectors. Then copy module 0 to 0x400000 and call it: the game's code will
; cause an exception. Report it on COM1 and halt:
;     exception <vector, decimal> at 0x<the eip the CPU pushed, 8 hex digits>
; followed, for the exceptions that push an error code, by
;     , error code 0x<8 hex digits>
; and CR LF. (Hex digits in lowercase.)

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start
_start:
    ; TODO
    cli
    hlt
