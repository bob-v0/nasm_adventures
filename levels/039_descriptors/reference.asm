; Level 39 — Descriptors (reference)

bits 16
org 0x7C00

start:
    cli
    xor ax, ax
    mov ds, ax
    lgdt [gdt_pointer]          ; GDTR = this table (only used once in protected mode)
    hlt

align 8
gdt:
    dq 0                        ; 0x00: the null descriptor
    ; 0x08: code. base 0, limit 0xFFFFF, access 0x9A (P, DPL 0, S, type 1010: exec/read),
    ; flags 0xC (G: 4 KiB units, D: 32-bit)
    dw 0xFFFF                   ; limit 0-15
    dw 0                        ; base 0-15
    db 0                        ; base 16-23
    db 10011010b                ; access
    db 11001111b                ; flags (high nibble), limit 16-19 (low nibble)
    db 0                        ; base 24-31
    ; 0x10: data, the same with type 0010 (read/write)
    dw 0xFFFF, 0
    db 0, 10010010b, 11001111b, 0
gdt_end:

gdt_pointer:
    dw gdt_end - gdt - 1        ; the limit: size minus one
    dd gdt                      ; the base: a linear address

times 510 - ($ - $$) db 0
dw 0xAA55
