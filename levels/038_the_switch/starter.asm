; Level 38 — The Switch
;
; Switch to 32-bit protected mode, then:
;   - load ds, es, ss (and fs, gs) with the data selector 0x10, and set up a stack;
;   - write PROTECTED MODE somewhere on the screen (video memory at 0xB8000);
;   - send "Hello from protected mode!" and CR LF to COM1 (0x3F8);
;   - halt.

bits 16
org 0x7C00

start:
    cli
    xor ax, ax
    mov ds, ax
    lgdt [gdt_pointer]
    ; TODO
    hlt

align 8
gdt:
    dq 0
    dq 0x00CF9A000000FFFF       ; 0x08: flat code (level 39)
    dq 0x00CF92000000FFFF       ; 0x10: flat data
gdt_end:
gdt_pointer:
    dw gdt_end - gdt - 1
    dd gdt

times 510 - ($ - $$) db 0
dw 0xAA55
