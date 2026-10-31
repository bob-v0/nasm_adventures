; Level 34 — Silencing the PIC
;
; The legacy 8259 PICs are still in every PC, delivering IRQs as vectors 8-15 (which
; protected mode uses for exceptions). Before the APIC takes over (levels 33 and 32):
;   - remap them: IRQ 0-7 to vectors 0x20-0x27, IRQ 8-15 to 0x28-0x2F;
;   - mask every line on both;
;   - handle a spurious IRQ 7 (vector 0x27): if the master's in-service register says
;     IRQ 7 isn't in service, count it in the global dword `spurious` and send no EOI.
; Then the game's module (module 0, run at 0x400000) checks your work.

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
    ; TODO: gates for 0x27 (and 0x2F), lidt, remap the PICs, mask them
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

; TODO: the IRQ 7 handler (and IRQ 15's)

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
