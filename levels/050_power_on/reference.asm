; Level 50 — Power On (reference)

bits 16
org 0x7C00                      ; the BIOS loads us here: labels are real addresses

start:
    cli
    xor ax, ax
    mov ds, ax                  ; (SeaBIOS starts us with ds = 0; level 48 is about others)
    mov bx, magic
    mov ax, 0xF000
    mov es, ax
    mov si, [es:0xFFF3]         ; the reset vector: EA, offset, segment
    mov di, [es:0xFFF1]
    mov ax, [bx]                ; 0xB007
    hlt

magic: dw 0xB007

times 510 - ($ - $$) db 0
dw 0xAA55
