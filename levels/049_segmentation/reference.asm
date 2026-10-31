; Level 49 — Segmentation (reference)
;
; Assembled for offset 0 in segment 0x07C0: 07C0:0000 is the same byte as 0000:7C00.

bits 16
org 0

start:
    jmp 0x07C0:.go              ; cs = 0x07C0, whatever the BIOS used
.go:
    cli
    mov ax, cs
    mov ds, ax                  ; our labels are offsets in this segment
    mov ss, ax
    mov sp, 0xFE00              ; a stack above us in the same 64 KiB
    mov si, hello
    call print
    xor ax, ax
    mov ds, ax
    lds si, [0x0500]            ; the far pointer: si = offset, ds = segment
    call print
    mov ax, cs
    mov ds, ax
    mov si, newline
    call print
    mov si, date
    call print
    mov ax, 0xF000
    mov ds, ax
    mov si, 0xFFF5              ; F000:FFF5 = physical FFFF5
    mov cx, 8
    mov ah, 0x0E
    xor bh, bh
.date:
    lodsb
    int 0x10
    loop .date
    hlt

print:                          ; ds:si = a NUL-terminated string
    mov ah, 0x0E
    xor bh, bh
.next:
    lodsb
    test al, al
    jz .done
    int 0x10
    jmp .next
.done:
    ret

hello:   db "Hello, segments!", 13, 10, 0
newline: db 13, 10, 0
date:    db "BIOS date: ", 0

times 510 - ($ - $$) db 0
dw 0xAA55
