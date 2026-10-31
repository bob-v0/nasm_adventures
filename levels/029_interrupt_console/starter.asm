; Level 29 — Interrupt-Driven Console (boss)
;
; A console with two inputs: the keyboard, and a terminal on the second serial port, COM2
; (port 0x2F8, ISA IRQ 3). People type on both at once. Each finished line is printed on
; COM1 with its source:
;     kbd: hello world
;     com2: Hello, COM2!
; Backspace works on both. When both have sent the line `bye`: print `bye`, then cli; hlt.
;
; All of it interrupt-driven, through the APIC: no polling loops, and the timer ticks
; at 100 Hz the whole time (`ticks`, a global dword).

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1
COM1     equ 0x3F8
COM2     equ 0x2F8

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start, ticks
_start:
    mov esp, stack_top
    lgdt [gdt_pointer]
    jmp 0x08:.reload
.reload:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    call silence_pic
    ; your kernel

    mov esi, s_ready            ; then: "ready", and the console runs
    call puts
    cli
    hlt

; ---- helpers ------------------------------------------------------------------------

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
    mov dx, COM1 + 5
.ready:
    in al, dx
    test al, 0x20
    jz .ready
    pop eax
    mov dx, COM1
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
keymap:
    db 0, 0, "1234567890", 0, 0, 0, 0
    db "qwertyuiop", 0, 0, 0, 0
    db "asdfghjkl", 0, 0, 0, 0, 0
    db "zxcvbnm", 0, 0, 0, 0, 0, 0, " "
s_ready: db "ready", 13, 10, 0
s_bye:   db "bye", 13, 10, 0
s_kbd:   db "kbd: ", 0
s_com:   db "com2: ", 0
crlf:    db 13, 10, 0


section .bss
alignb 4
ticks:  resd 1
alignb 8
idt:    resq 256
alignb 16
stack:  resb 8192
stack_top:
