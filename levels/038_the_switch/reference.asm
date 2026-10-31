; Level 38 — The Switch (reference)

bits 16
org 0x7C00

start:
    cli                         ; no interrupts from here on: there's no IDT for them
    xor ax, ax
    mov ds, ax
    lgdt [gdt_pointer]
    mov eax, cr0
    or eax, 1                   ; PE: protected mode on
    mov cr0, eax
    jmp 0x08:protected          ; a far jump loads cs from the GDT and flushes the old mode

bits 32
protected:
    mov ax, 0x10                ; every data segment register: the flat data selector
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax
    mov esp, 0x90000
    mov esi, banner             ; on the screen, through 32-bit addresses
    mov edi, 0xB8000 + 12 * 160 + 33 * 2
    mov ah, 0x1F
.screen:
    lodsb
    test al, al
    jz .serial
    stosw
    jmp .screen
.serial:
    mov esi, hello
.next:
    lodsb
    test al, al
    jz .done
    mov ah, al
    mov dx, 0x3FD
.wait:
    in al, dx
    test al, 0x20
    jz .wait
    mov al, ah
    mov dx, 0x3F8
    out dx, al
    jmp .next
.done:
    hlt

banner: db "PROTECTED MODE", 0
hello:  db "Hello from protected mode!", 13, 10, 0

align 8
gdt:
    dq 0
    dq 0x00CF9A000000FFFF       ; 0x08: flat code
    dq 0x00CF92000000FFFF       ; 0x10: flat data
gdt_end:
gdt_pointer:
    dw gdt_end - gdt - 1
    dd gdt

times 510 - ($ - $$) db 0
dw 0xAA55
