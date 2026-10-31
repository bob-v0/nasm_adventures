; Level 36 — Exceptions (reference)

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1
MODULE   equ 0x400000

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start
_start:
    mov esp, stack_top
    lgdt [gdt_pointer]          ; our own GDT: the loader's may be anywhere
    jmp 0x08:.reload
.reload:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax
    xor ecx, ecx                ; the IDT: 32 interrupt gates, one per exception
.gate:
    mov eax, [stubs + ecx * 4]
    mov [idt + ecx * 8], ax             ; offset 0-15
    mov word [idt + ecx * 8 + 2], 0x08  ; the code selector
    mov word [idt + ecx * 8 + 4], 0x8E00 ; present, DPL 0, 32-bit interrupt gate
    shr eax, 16
    mov [idt + ecx * 8 + 6], ax         ; offset 16-31
    inc ecx
    cmp ecx, 32
    jb .gate
    lidt [idt_pointer]
    mov esi, [ebx + 24]         ; module 0: copy it to MODULE, and call it
    mov ecx, [esi + 4]
    mov esi, [esi]
    sub ecx, esi
    mov edi, MODULE
    rep movsb
    call MODULE
    cli
    hlt

; the stubs: push a dummy error code where the CPU pushes none, then the vector
%macro STUB 1
stub%1:
%if %1 == 8 || (%1 >= 10 && %1 <= 14) || %1 == 17 || %1 == 21 || %1 == 29 || %1 == 30
    push dword %1
%else
    push dword 0
    push dword %1
%endif
    jmp exception
%endmacro
%assign n 0
%rep 32
    STUB n
%assign n n + 1
%endrep

exception:                      ; [esp] vector, [esp + 4] error code, [esp + 8] eip
    mov esi, s_exception
    call puts
    mov eax, [esp]
    call decimal
    mov esi, s_at
    call puts
    mov eax, [esp + 8]
    call hex
    mov ecx, [esp]
    bt dword [has_error], ecx
    jnc .end
    mov esi, s_error
    call puts
    mov eax, [esp + 4]
    call hex
.end:
    mov esi, crlf
    call puts
    cli
    hlt

hex:                            ; eax as 0x and 8 digits
    push eax
    mov esi, s_0x
    call puts
    pop edx
    mov ecx, 8
.digit:
    rol edx, 4
    mov eax, edx
    and eax, 15
    mov al, [digits + eax]
    call putc
    loop .digit
    ret

decimal:
    mov ebx, 10
    xor ecx, ecx
.d:
    xor edx, edx
    div ebx
    push edx
    inc ecx
    test eax, eax
    jnz .d
.o:
    pop eax
    add al, '0'
    call putc
    loop .o
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
    dw 32 * 8 - 1
    dd idt
stubs:
%assign n 0
%rep 32
    dd stub %+ n
%assign n n + 1
%endrep
has_error: dd 1 << 8 | 1 << 10 | 1 << 11 | 1 << 12 | 1 << 13 | 1 << 14 | 1 << 17 | 1 << 21 | 1 << 29 | 1 << 30
digits: db "0123456789abcdef"
s_exception: db "exception ", 0
s_at: db " at ", 0
s_error: db ", error code ", 0
s_0x: db "0x", 0
crlf: db 13, 10, 0

section .bss
alignb 8
idt: resq 32
alignb 16
stack: resb 8192
stack_top:
