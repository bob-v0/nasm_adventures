; Level 45 — Disk (reference)

bits 16
org 0x7C00

STAGE2 equ 0x8000

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
    mov [drive], dl
    mov word [dap.count], 1     ; first the header: one sector, LBA 1
    call read
    cmp word [STAGE2], 0x5A2B
    jne fail
    mov ax, [STAGE2 + 2]        ; then all of it
    mov [dap.count], ax
    call read
    mov dl, [drive]
    jmp 0:STAGE2 + 4

read:                           ; int 13h, ah = 42h: read sectors by LBA (the DAP below)
    mov ah, 0x42
    mov dl, [drive]
    mov si, dap
    int 0x13
    jc fail
    ret

fail:
    mov si, error
.print:
    lodsb
    test al, al
    jz .stop
    mov ah, 0x0E
    xor bh, bh
    int 0x10
    jmp .print
.stop:
    cli
    hlt

drive: db 0
error: db "disk error", 0
align 4
dap:                            ; the disk address packet
    db 16, 0                    ; its size; reserved
.count: dw 1                    ; sectors to read
    dw STAGE2, 0                ; where: offset, segment
    dq 1                        ; the first sector, by LBA (0 is this one)

times 510 - ($ - $$) db 0
dw 0xAA55
