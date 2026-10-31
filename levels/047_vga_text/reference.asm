; Level 47 — VGA Text Mode (reference)

bits 16
org 0x7C00

BG     equ 0x17
BORDER equ 0x1E
INSIDE equ 0x3F
STATUS equ 0x70
LEFT   equ 20
TOP    equ 8
RIGHT  equ 59
BOTTOM equ 16

start:
    jmp 0:.go
.go:
    cli
    xor ax, ax
    mov ds, ax
    mov ss, ax
    mov sp, 0x7C00
    mov ax, 0xB800              ; text mode memory: B800:0000 = physical B8000
    mov es, ax
    cld
    xor di, di                  ; the background: 80 x 25 cells of (' ', BG)
    mov ax, BG << 8 | ' '
    mov cx, 80 * 25
    rep stosw
    mov bx, TOP                 ; the box's rows
.row:
    mov ax, bx
    imul di, ax, 160
    add di, LEFT * 2
    cmp bx, TOP
    je .edge
    cmp bx, BOTTOM
    je .edge
    mov ax, BORDER << 8 | 0xBA  ; ║, inside, ║
    stosw
    mov ax, INSIDE << 8 | ' '
    mov cx, RIGHT - LEFT - 1
    rep stosw
    mov ax, BORDER << 8 | 0xBA
    stosw
    jmp .next
.edge:
    mov dx, 0xBBC9              ; ╔ ╗ on top
    cmp bx, TOP
    je .corners
    mov dx, 0xBCC8              ; ╚ ╝ at the bottom
.corners:
    mov al, dl
    mov ah, BORDER
    stosw
    mov al, 0xCD                ; ═
    mov cx, RIGHT - LEFT - 1
    rep stosw
    mov al, dh
    stosw
.next:
    inc bx
    cmp bx, BOTTOM
    jbe .row
    mov si, title               ; the title, centered
    mov di, 12 * 160 + (LEFT + 1 + (RIGHT - LEFT - 1 - TITLE_LEN) / 2) * 2
    mov ah, INSIDE
    call text
    mov di, 24 * 160            ; the status line: its whole row
    mov ax, STATUS << 8 | ' '
    mov cx, 80
    rep stosw
    mov di, 24 * 160
    mov si, status
    mov ah, STATUS
    call text
    hlt

text:                           ; ds:si = NUL-terminated, es:di = the first cell, ah = attribute
    lodsb
    test al, al
    jz .done
    stosw
    jmp text
.done:
    ret

title:  db "NASM ADVENTURES", 0
TITLE_LEN equ $ - title - 1
status: db " Level 47: VGA text mode", 0

times 510 - ($ - $$) db 0
dw 0xAA55
