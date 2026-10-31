; Level 33 — Local APIC
;
; Drive time with the Local APIC: enable it (spurious vector 0xFF), calibrate its timer
; against the PIT, and run it periodically at 100 Hz on vector 0x40. Its handler adds 1
; to `ticks` and sends the APIC an EOI. The legacy PIC stays remapped and masked
; (silence_pic, from level 34). Then the kernel calls the game's module at 0x400000 with
; eax = the address of `ticks`: it measures the rate against the CMOS clock.

bits 32

MB_FLAGS  equ 1 << 0 | 1 << 1
MODULE    equ 0x400000
APIC_BASE_MSR equ 0x1B
SVR       equ 0xF0              ; Local APIC registers: offsets from its base
EOI       equ 0xB0
LVT_TIMER equ 0x320
INITIAL   equ 0x380
CURRENT   equ 0x390
DIVIDE    equ 0x3E0
TIMER_VECTOR equ 0x40

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start, ticks
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
    mov eax, timer
    mov ecx, TIMER_VECTOR
    call set_gate
    mov eax, spurious
    mov ecx, 0xFF
    call set_gate
    lidt [idt_pointer]
    call silence_pic            ; level 34
    ; TODO: find and enable the Local APIC, calibrate its timer against the PIT,
    ; and start it at 100 Hz
    mov ebx, [boot_info]        ; the game's module measures it
    mov esi, [ebx + 24]
    mov ecx, [esi + 4]
    mov esi, [esi]
    sub ecx, esi
    mov edi, MODULE
    rep movsb
    mov eax, ticks
    call MODULE
    cli
    mov esi, s_done
    call puts
    hlt

timer:                          ; TODO: count, EOI
    iret

spurious:                       ; TODO
    iret

silence_pic:                    ; remap the 8259s to 0x20/0x28 and mask them all
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
s_done: db "done", 13, 10, 0

section .bss
alignb 4
ticks:     resd 1
apic:      resd 1
boot_info: resd 1
alignb 8
idt: resq 256
alignb 16
stack: resb 8192
stack_top:
