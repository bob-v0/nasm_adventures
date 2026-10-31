; Level 44 — Real-Mode Interrupts (reference)

bits 16
org 0x7C00

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
    mov word [0x80 * 4], int80  ; the IVT entry: offset, then segment
    mov word [0x80 * 4 + 2], 0
    sti
    mov [drive], dl
    mov ah, 0x42                ; load the game's test program (2 sectors from LBA 1)
    mov si, dap
    int 0x13
    mov dl, [drive]
    jmp 0:PROGRAM + 4

; int 0x80: ah = 0: putc al; 1: ax = bx + cx; 2: puts ds:si, cx = its length.
; Everything else is preserved; the carry flag says whether it worked.
int80:
    cmp ah, 2
    ja .unknown
    push bp
    mov bp, sp                  ; [bp+2] ip, [bp+4] cs, [bp+6] flags
    and byte [bp + 6], 0xFE     ; clear CF in the flags iret will restore
    pop bp
    cmp ah, 1
    jb .putc
    je .add
    push si                     ; puts
    xor cx, cx
.next:
    lodsb
    test al, al
    jz .end
    call serial
    inc cx
    jmp .next
.end:
    pop si
    iret
.add:
    mov ax, bx
    add ax, cx
    iret
.putc:
    call serial
    iret
.unknown:
    push bp
    mov bp, sp
    or byte [bp + 6], 1         ; set CF in the caller's flags
    pop bp
    iret

serial:                         ; al -> COM1; keeps every register
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

drive: db 0
align 4
dap: db 16, 0
     dw 2, PROGRAM, 0
     dq 1

times 510 - ($ - $$) db 0
dw 0xAA55
