; Level 43 — Keyboard (reference)

bits 16
org 0x7C00

MAX equ 70
ROW equ 12                      ; where the line is shown on the screen

start:
    jmp 0:.go
.go:
    cli                         ; for good: the BIOS's keyboard interrupt would eat our scancodes
    xor ax, ax
    mov ds, ax
    mov ss, ax
    mov sp, 0x7C00
    mov ax, 0xB800
    mov es, ax
    mov si, prompt
    call puts
    xor bx, bx                  ; the line's length
.key:
    in al, 0x64                 ; status: bit 0 = a byte is waiting at port 0x60
    test al, 1
    jz .key
    in al, 0x60                 ; a scancode (set 1)
    cmp al, 0x2A                ; shift down / up
    je .shift_down
    cmp al, 0x36
    je .shift_down
    cmp al, 0xAA
    je .shift_up
    cmp al, 0xB6
    je .shift_up
    test al, 0x80               ; any other release: ignore
    jnz .key
    cmp al, 0x1C
    je .enter
    cmp al, 0x0E
    je .backspace
    cmp al, 0x39
    ja .key
    mov si, ax
    and si, 0xFF
    mov al, [keymap + si]       ; scancode -> character
    test al, al
    jz .key
    cmp byte [shift], 0
    je .store
    cmp al, 'a'
    jb .store
    cmp al, 'z'
    ja .store
    sub al, 'a' - 'A'
.store:
    cmp bx, MAX
    jae .key
    mov [line + bx], al
    mov ah, 0x07                ; echo it on the screen
    mov di, bx
    shl di, 1
    mov [es:ROW * 160 + di], ax
    inc bx
    jmp .key
.backspace:
    test bx, bx
    jz .key
    dec bx
    mov di, bx
    shl di, 1
    mov word [es:ROW * 160 + di], 0x0720
    jmp .key
.shift_down:
    mov byte [shift], 1
    jmp .key
.shift_up:
    mov byte [shift], 0
    jmp .key
.enter:
    mov byte [line + bx], 0
    mov si, line
    call puts
    mov si, crlf
    call puts
    hlt

puts:                           ; ds:si -> COM1
    lodsb
    test al, al
    jz .done
    push ax
    mov dx, 0x3FD
.wait:
    in al, dx
    test al, 0x20
    jz .wait
    pop ax
    mov dx, 0x3F8
    out dx, al
    jmp puts
.done:
    ret

keymap:                         ; set 1 scancodes 0x00-0x39 (0: no character)
    db 0, 0, "1234567890-=", 0, 0
    db "qwertyuiop[]", 0, 0
    db "asdfghjkl;'`", 0, "\"
    db "zxcvbnm,./", 0, "*", 0, " "
prompt: db "> ", 0
crlf:   db 13, 10, 0
shift:  db 0
line:   times MAX + 1 db 0

times 510 - ($ - $$) db 0
dw 0xAA55
