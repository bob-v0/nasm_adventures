; Level 34 — Silencing the PIC (reference)

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1
MODULE   equ 0x400000

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start, spurious
_start:
    mov esp, stack_top
    mov [boot_info], ebx
    lgdt [gdt_pointer]
    jmp 0x08:.reload
.reload:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov eax, irq7               ; the legacy PIC's IRQ 7 (vector 0x27) and IRQ 15 (0x2F)
    mov ecx, 0x27               ; can arrive without any device asking: spurious
    call set_gate
    mov eax, irq15
    mov ecx, 0x2F
    call set_gate
    lidt [idt_pointer]
    mov al, 0x11                ; remap: ICW1 ...
    out 0x20, al
    out 0xA0, al
    mov al, 0x20                ; ICW2: vectors 0x20-0x27 and 0x28-0x2F,
    out 0x21, al                ; away from the CPU's exceptions (0-31)
    mov al, 0x28
    out 0xA1, al
    mov al, 0x04                ; ICW3: the slave hangs off the master's IRQ 2
    out 0x21, al
    mov al, 0x02
    out 0xA1, al
    mov al, 0x01                ; ICW4: 8086 mode
    out 0x21, al
    out 0xA1, al
    mov al, 0xFF                ; and mask everything: the APIC takes over (levels 33, 32)
    out 0x21, al
    out 0xA1, al
    mov ebx, [boot_info]        ; the game's module checks all that
    mov esi, [ebx + 24]
    mov ecx, [esi + 4]
    mov esi, [esi]
    sub ecx, esi
    mov edi, MODULE
    rep movsb
    call MODULE
    mov esi, s_done
    call puts
    cli
    hlt

irq7:                           ; real IRQ 7, or spurious? Ask the master's in-service register
    push eax
    mov al, 0x0B                ; OCW3: read the ISR next
    out 0x20, al
    in al, 0x20
    test al, 0x80
    jz .spurious
    mov al, 0x20                ; a real one: EOI
    out 0x20, al
    pop eax
    iret
.spurious:
    inc dword [spurious]        ; no EOI: nothing is in service for IRQ 7
    pop eax
    iret

irq15:                          ; the same on the slave; a spurious IRQ 15 still owes the
    push eax                    ; master an EOI (for its IRQ 2, the cascade)
    mov al, 0x0B
    out 0xA0, al
    in al, 0xA0
    test al, 0x80
    jz .spurious
    mov al, 0x20
    out 0xA0, al
    out 0x20, al
    pop eax
    iret
.spurious:
    inc dword [spurious]
    mov al, 0x20
    out 0x20, al
    pop eax
    iret

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
s_done: db "done", 13, 10, 0

section .bss
alignb 4
spurious:  resd 1
boot_info: resd 1
alignb 8
idt: resq 256
alignb 16
stack: resb 8192
stack_top:
