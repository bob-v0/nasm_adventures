; Level 42 — PIT & PIC (reference)

bits 16
org 0x7C00

PIT_HZ  equ 1193182             ; the PIT's input clock
DIVISOR equ (PIT_HZ + 50) / 100 ; 100 interrupts per second (11932)
PROGRAM equ 0x8000

start:
    jmp 0:.go
.go:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00
    mov dword [0x0500], 0
    mov word [8 * 4], tick      ; IRQ 0 is vector 8 in real mode (the BIOS's PIC setup)
    mov word [8 * 4 + 2], 0
    mov al, 0x36                ; PIT: channel 0, lobyte/hibyte, mode 3 (square wave)
    out 0x43, al
    mov ax, DIVISOR
    out 0x40, al
    mov al, ah
    out 0x40, al
    in al, 0x21                 ; PIC: unmask IRQ 0
    and al, 0xFE
    out 0x21, al
    mov [drive], dl
    sti
    mov ah, 0x42                ; load the game's test program
    mov si, dap
    int 0x13
    mov dl, [drive]
    jmp 0:PROGRAM + 4

tick:                           ; IRQ 0: count, and tell the PIC we're done
    inc dword [cs:0x0500]
    push ax
    mov al, 0x20                ; EOI (end of interrupt) to the master PIC
    out 0x20, al
    pop ax
    iret

drive: db 0
align 4
dap: db 16, 0
     dw 2, PROGRAM, 0
     dq 1

times 510 - ($ - $$) db 0
dw 0xAA55
