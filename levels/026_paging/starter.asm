; Level 26 — 4-Level Paging
;
; Build the page tables a 64-bit kernel runs on (level 25 switches them on). Three
; regions, each covering the first 1 GiB of physical memory:
;
;   identity     virtual 0 + x                  -> physical x    (except x < 4096)
;   higher half  virtual 0xFFFFFFFF80000000 + x -> physical x
;   direct map   virtual 0xFFFF800000000000 + x -> physical x    no-execute
;
; Everything writable, nothing reachable from user mode. The first 4 KiB of the identity
; map stay unmapped: a null pointer must fault. Anything else: not mapped.
; Use 2 MiB pages where you can. Halt with eax = the PML4's physical address.
;
; Paging stays off in this level (32-bit code can't use 4-level tables): the game walks
; your tables the way the CPU will.

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1
P        equ 1 << 0             ; present
W        equ 1 << 1             ; writable
PS       equ 1 << 7             ; (in a PD entry) a 2 MiB page
NX_HIGH  equ 1 << 31            ; bit 63 of an entry: bit 31 of its high dword

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start
_start:
    mov esp, stack_top
    ; your tables

    mov eax, pml4
    cli
    hlt

section .bss
alignb 4096                     ; a table: 512 entries of 8 bytes, 4 KiB aligned
pml4:      resq 512
alignb 16
stack:     resb 4096
stack_top:
