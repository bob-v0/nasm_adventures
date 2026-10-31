; Level 46 — Port I/O (reference)

bits 16
org 0x7C00

COM1 equ 0x3F8                  ; the 16550's registers are COM1 + 0 ... + 7
CMOS equ 0x70                   ; index port; data at 0x71

start:
    jmp 0:.go
.go:
    cli
    xor ax, ax
    mov ds, ax
    mov ss, ax
    mov sp, 0x7C00
    mov dx, COM1 + 1            ; IER: no UART interrupts
    xor al, al
    out dx, al
    mov dx, COM1 + 3            ; LCR: DLAB = 1, to set the baud rate divisor
    mov al, 0x80
    out dx, al
    mov dx, COM1                ; divisor 1: 115200 baud (low byte, then high)
    mov al, 1
    out dx, al
    inc dx
    xor al, al
    out dx, al
    mov dx, COM1 + 3            ; LCR: 8 data bits, no parity, 1 stop bit; DLAB = 0
    mov al, 0x03
    out dx, al
    mov si, hello
    call puts
    mov al, 0x32                ; century, year, month, day: BCD in CMOS registers
    call bcd
    mov al, 0x09
    call bcd
    mov al, '-'
    call putc
    mov al, 0x08
    call bcd
    mov al, '-'
    call putc
    mov al, 0x07
    call bcd
    mov si, tail
    call puts
    hlt

bcd:                            ; print CMOS register al: two BCD digits
    out CMOS, al
    in al, CMOS + 1
    mov ah, al
    shr al, 4
    add al, '0'
    call putc
    mov al, ah
    and al, 0x0F
    add al, '0'
    jmp putc

puts:                           ; ds:si = a NUL-terminated string
    lodsb
    test al, al
    jz .done
    call putc
    jmp puts
.done:
    ret

putc:                           ; al -> COM1, when the transmitter can take it
    push dx
    push ax
    mov dx, COM1 + 5            ; LSR: bit 5 = the transmit holding register is empty
.wait:
    in al, dx
    test al, 0x20
    jz .wait
    pop ax
    mov dx, COM1
    out dx, al
    pop dx
    ret

hello: db "Hello, serial port! Today is ", 0
tail:  db ".", 13, 10, 0

times 510 - ($ - $$) db 0
dw 0xAA55
