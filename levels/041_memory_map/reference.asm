; Level 41 — Memory Map & A20 (reference)

bits 16
org 0x7C00

BUFFER equ 0x0600               ; one 24-byte E820 entry

start:
    jmp 0:.go
.go:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00
    sti
    xor ebx, ebx                ; E820: ebx = 0 for the first entry, then what it returns
.entry:
    mov eax, 0xE820
    mov edx, 0x534D4150         ; 'SMAP'
    mov ecx, 24
    mov di, BUFFER
    int 0x15
    jc .done                    ; (carry: past the end, on some BIOSes)
    cmp eax, 0x534D4150
    jne .done
    mov eax, [BUFFER + 4]       ; base: high dword, low dword
    call hex32
    mov eax, [BUFFER]
    call hex32
    mov al, ' '
    call putc
    mov eax, [BUFFER + 12]      ; length
    call hex32
    mov eax, [BUFFER + 8]
    call hex32
    mov al, ' '
    call putc
    mov al, [BUFFER + 16]       ; type: 1 usable, 2 reserved, 3 ACPI, ...
    add al, '0'
    call putc
    call newline
    test ebx, ebx               ; 0: that was the last one
    jnz .entry
.done:
    in al, 0x92                 ; A20 on: the "fast A20" bit of port 0x92
    or al, 2
    and al, 0xFE                ; (bit 0 would reset the machine)
    out 0x92, al
    mov ax, 0xFFFF              ; does FFFF:0510 (= 0x100500) still wrap to 0000:0500?
    mov fs, ax
    mov byte [0x0500], 0x11
    mov byte [fs:0x0510], 0x22
    cmp byte [0x0500], 0x11
    jne .wraps
    mov si, a20_on
    call puts
    cli
    hlt
.wraps:
    mov si, a20_off
    call puts
    cli
    hlt

hex32:                          ; eax as 8 hex digits
    mov cx, 8
.digit:
    rol eax, 4
    push eax
    and al, 15
    add al, '0'
    cmp al, '9'
    jbe .print
    add al, 'a' - '9' - 1
.print:
    call putc
    pop eax
    loop .digit
    ret

newline:
    mov al, 13
    call putc
    mov al, 10
putc:                           ; al -> COM1
    push dx
    push ax
    mov dx, 0x3FD
.wait:
    in al, dx
    test al, 0x20
    jz .wait
    pop ax
    mov dx, 0x3F8
    out dx, al
    pop dx
    ret

puts:
    lodsb
    test al, al
    jz .end
    call putc
    jmp puts
.end:
    ret

a20_on:  db "A20 is on", 13, 10, 0
a20_off: db "A20 is still off", 13, 10, 0

times 510 - ($ - $$) db 0
dw 0xAA55
