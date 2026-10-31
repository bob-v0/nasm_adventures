; Level 39 — Descriptors
;
; Build a Global Descriptor Table for a flat 32-bit world, and load it with lgdt
; (staying in real mode: level 38 switches). Then halt.
;   entry 0 (selector 0x00): the null descriptor
;   entry 1 (selector 0x08): code: base 0, 4 GiB, ring 0, execute/read, 32-bit
;   entry 2 (selector 0x10): data: base 0, 4 GiB, ring 0, read/write, 32-bit

bits 16
org 0x7C00

start:
    cli
    xor ax, ax
    mov ds, ax
    ; TODO: lgdt
    hlt

align 8
gdt:
    dq 0
    ; TODO: the code and data descriptors
gdt_end:

times 510 - ($ - $$) db 0
dw 0xAA55
