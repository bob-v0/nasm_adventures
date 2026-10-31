; Level 32 — I/O APIC (reference)

bits 32

MB_FLAGS   equ 1 << 0 | 1 << 1
APIC_EOI   equ 0xB0
APIC_SVR   equ 0xF0
IOAPIC     equ 0xFEC00000       ; IOREGSEL at +0x00, IOWIN at +0x10
KBD_VECTOR equ 0x41

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start
_start:
    mov esp, stack_top
    lgdt [gdt_pointer]
    jmp 0x08:.reload
.reload:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov eax, keyboard
    mov ecx, KBD_VECTOR
    call set_gate
    mov eax, spurious
    mov ecx, 0xFF
    call set_gate
    lidt [idt_pointer]
    call silence_pic            ; level 34
    mov ecx, 0x1B               ; the Local APIC, enabled (level 33): it delivers what
    rdmsr                       ; the I/O APIC sends, and takes the EOIs
    and eax, 0xFFFFF000
    mov [apic], eax
    mov dword [eax + APIC_SVR], 0x1FF
    ; the I/O APIC: redirection entry 1 (ISA IRQ 1, the keyboard) is registers 0x12 (low)
    ; and 0x13 (high): select a register through IOREGSEL, then read/write IOWIN
    mov dword [IOAPIC], 0x12
    mov dword [IOAPIC + 0x10], KBD_VECTOR   ; fixed delivery, physical, edge, active high,
                                            ; unmasked (bit 16 clear), this vector
    mov dword [IOAPIC], 0x13
    mov dword [IOAPIC + 0x10], 0            ; destination: APIC ID 0 (bits 56-63)
    mov esi, s_ready
    call puts
    sti
main:
    cli                         ; check, then sleep with no gap between (level 30)
    mov eax, [tail]
    cmp eax, [head]
    jne .take
    sti
    hlt
    jmp main
.take:
    and eax, 15
    movzx ebx, byte [buffer + eax]
    inc dword [tail]
    sti
    test bl, 0x80               ; releases: ignore
    jnz main
    cmp bl, 0x01                ; Esc
    je .bye
    cmp bl, 0x1C                ; Enter
    je .enter
    cmp bl, 0x39
    ja main
    mov al, [keymap + ebx]
    test al, al
    jz main
    call putc
    jmp main
.enter:
    mov esi, crlf
    call puts
    jmp main
.bye:
    mov esi, s_bye
    call puts
    cli
    hlt

keyboard:                       ; the scancode into the ring buffer
    push eax
    push ebx
    in al, 0x60
    mov ebx, [head]
    sub ebx, [tail]
    cmp ebx, 16
    jae .full                   ; (full: drop it)
    mov ebx, [head]
    and ebx, 15
    mov [buffer + ebx], al
    inc dword [head]            ; publish it after it's written
.full:
    mov ebx, [apic]
    mov dword [ebx + APIC_EOI], 0
    pop ebx
    pop eax
    iret

spurious:
    iret

silence_pic:
    mov al, 0x11
    out 0x20, al
    out 0xA0, al
    mov al, 0x20
    out 0x21, al
    mov al, 0x28
    out 0xA1, al
    mov al, 0x04
    out 0x21, al
    mov al, 0x02
    out 0xA1, al
    mov al, 0x01
    out 0x21, al
    out 0xA1, al
    mov al, 0xFF
    out 0x21, al
    out 0xA1, al
    ret

set_gate:                       ; ecx = vector, eax = handler
    mov [idt + ecx * 8], ax
    mov word [idt + ecx * 8 + 2], 0x08
    mov word [idt + ecx * 8 + 4], 0x8E00
    shr eax, 16
    mov [idt + ecx * 8 + 6], ax
    ret

putc:
    push edx
    push eax
    mov dx, 0x3FD
.wait:
    in al, dx
    test al, 0x20
    jz .wait
    pop eax
    mov dx, 0x3F8
    out dx, al
    pop edx
    ret

puts:
    lodsb
    test al, al
    jz .end
    call putc
    jmp puts
.end:
    ret

section .data
align 8
gdt:
    dq 0
    dq 0x00CF9A000000FFFF
    dq 0x00CF92000000FFFF
gdt_end:
gdt_pointer:
    dw gdt_end - gdt - 1
    dd gdt
idt_pointer:
    dw 256 * 8 - 1
    dd idt
keymap:                         ; set 1 scancodes 0x00-0x39 (0: nothing)
    db 0, 0, "1234567890", 0, 0, 0, 0
    db "qwertyuiop", 0, 0, 0, 0
    db "asdfghjkl", 0, 0, 0, 0, 0
    db "zxcvbnm", 0, 0, 0, 0, 0, 0, " "  ; (0x39: space)
s_ready: db "ready", 13, 10, 0
s_bye:   db 13, 10, "bye", 13, 10, 0
crlf:    db 13, 10, 0

section .bss
alignb 4
apic:   resd 1
head:   resd 1                  ; written by the keyboard handler only
tail:   resd 1                  ; written by the main loop only
buffer: resb 16
alignb 8
idt:    resq 256
alignb 16
stack:  resb 8192
stack_top:
