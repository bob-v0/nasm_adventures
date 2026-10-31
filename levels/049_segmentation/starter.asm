; Level 49 — Segmentation
;
; Print three lines with the BIOS (int 10h, ah = 0x0E), then halt:
;   Hello, segments!
;   <the note the game left for you>
;   BIOS date: <8 characters>
;
; The note is a NUL-terminated string somewhere in the first megabyte; a far pointer
; to it (offset word, then segment word) is at 0000:0500. The BIOS's date is the 8
; characters at F000:FFF5.

bits 16
org 0x7C00

start:
    cli
    xor ax, ax
    mov ds, ax
    mov ss, ax
    mov sp, 0x7C00
    mov si, hello
    call print
    ; TODO: the note, then "BIOS date: " and the date
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

hello: db "Hello, segments!", 13, 10, 0
date:  db "BIOS date: ", 0

times 510 - ($ - $$) db 0
dw 0xAA55
