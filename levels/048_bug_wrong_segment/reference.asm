; Level 48 — Wrong Segment (reference)
;! witness bios = "odd"
;
; This boot sector prints a little menu of what it would boot. It works in QEMU.
; Users report a blank screen, or garbage, on their machines.
;
; 1. Find a BIOS it fails on. The game can hand over control the way SeaBIOS does
;    ("seabios") or the way some other BIOSes do ("odd"):   ;! witness bios = "odd"
; 2. Make it work on any BIOS.

bits 16
org 0x7C00

start:
    jmp 0:.normal               ; cs = 0, whatever the BIOS used: our offsets assume it
.normal:
    cli
    xor ax, ax
    mov ds, ax                  ; and so do our data references
    mov es, ax
    mov ss, ax                  ; a stack of our own, below us
    mov sp, 0x7C00
    sti
    mov si, title
    call print
    xor bx, bx
.entry:                         ; one line per menu entry
    mov si, [entries + bx]
    test si, si
    jz .done
    call [printer]              ; (the print routine, through a pointer)
    add bx, 2
    jmp .entry
.done:
    cli
    hlt

print:                          ; ds:si = a NUL-terminated string
    push bx
    mov ah, 0x0E
    xor bh, bh
.next:
    lodsb
    test al, al
    jz .end
    int 0x10
    jmp .next
.end:
    pop bx
    ret

printer: dw print
entries: dw linux, dos, 0
title:   db "Boot menu", 13, 10, 0
linux:   db "  1. Linux", 13, 10, 0
dos:     db "  2. FreeDOS", 13, 10, 0

times 510 - ($ - $$) db 0
dw 0xAA55
