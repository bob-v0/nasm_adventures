; Level 31 — Interrupt Reentrancy
;
; A producer in an interrupt handler, a consumer in the main loop. The APIC timer
; interrupts every `period` bus cycles (from the command line: "period=N"); its handler
; produces the numbers 1, 2, 3, ... 1000 into a 16-entry buffer. The main loop takes them
; out and checks that each is one more than the last. At the end it should say
;     received 1000 items in order, sum 500500
;
; With some periods it does. With others, items go missing or come twice.
;
; 1. Find a period that breaks it:   ;! witness period = N
; 2. Fix it, for every period.

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1
ITEMS    equ 1000
SLOTS    equ 16
APIC_EOI equ 0xB0
APIC_SVR equ 0xF0
LVT_TIMER equ 0x320
INITIAL  equ 0x380
DIVIDE   equ 0x3E0

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start
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
    mov ecx, 0x40
    call set_gate
    mov eax, spurious
    mov ecx, 0xFF
    call set_gate
    lidt [idt_pointer]
    call silence_pic
    call read_period            ; eax = the period from the command line
    mov ebx, eax
    mov ecx, 0x1B
    rdmsr
    and eax, 0xFFFFF000
    mov [apic], eax
    mov dword [eax + APIC_SVR], 0x1FF
    mov dword [eax + DIVIDE], 0xB       ; count at the bus clock itself (÷1)
    mov dword [eax + LVT_TIMER], 1 << 17 | 0x40
    mov [eax + INITIAL], ebx
    sti

consume:                        ; the main loop
    xor esi, esi                ; the last item
    xor edi, edi                ; the sum
.next:
    cmp esi, ITEMS
    je .done
    mov ecx, [count]            ; how many are waiting
    test ecx, ecx
    jz .next
    mov eax, [first]
    mov edx, [buffer + eax * 4] ; the oldest item
    inc eax
    and eax, SLOTS - 1
    mov [first], eax
    dec ecx
    mov [count], ecx            ; one fewer waiting
    inc esi
    cmp edx, esi
    jne .wrong
    add edi, edx
    jmp .next
.done:
    cli
    mov esi, s_ok
    call puts
    mov eax, edi
    call decimal
    mov esi, crlf
    call puts
    hlt
.wrong:
    cli
    push edx                    ; what arrived
    push esi                    ; what should have
    mov esi, s_wrong1
    call puts
    pop eax
    call decimal
    mov esi, s_wrong2
    call puts
    pop eax
    call decimal
    mov esi, crlf
    call puts
    hlt

timer:                          ; the producer: the next item, if there's room
    push eax
    push ebx
    mov eax, [produced]
    cmp eax, ITEMS
    jae .eoi
    cmp dword [count], SLOTS
    jae .eoi
    inc eax
    mov [produced], eax
    mov ebx, [first]            ; the free slot after the waiting ones
    add ebx, [count]
    and ebx, SLOTS - 1
    mov [buffer + ebx * 4], eax
    inc dword [count]
.eoi:
    mov ebx, [apic]
    mov dword [ebx + APIC_EOI], 0
    pop ebx
    pop eax
    iret

spurious:
    iret

read_period:                    ; "period=N" in the multiboot command line -> eax = N
    mov ebx, [boot_info]
    mov esi, [ebx + 16]
.find:
    lodsb
    test al, al
    jz .none
    cmp al, '='
    jne .find
    xor eax, eax
.digit:
    movzx ecx, byte [esi]
    sub ecx, '0'
    cmp ecx, 9
    ja .end
    imul eax, eax, 10
    add eax, ecx
    inc esi
    jmp .digit
.none:
    mov eax, 1000
.end:
    ret

silence_pic:                    ; level 34
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

decimal:                        ; eax
    push ebx
    push ecx
    push edx
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
    pop edx
    pop ecx
    pop ebx
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
s_ok:     db "received 1000 items in order, sum ", 0
s_wrong1: db "expected item ", 0
s_wrong2: db ", got ", 0
crlf:     db 13, 10, 0

section .bss
alignb 4
apic:      resd 1
boot_info: resd 1
produced:  resd 1               ; the producer's own
first:     resd 1               ; the consumer's: the oldest waiting slot
count:     resd 1               ; shared: how many are waiting
buffer:    resd SLOTS
alignb 8
idt:       resq 256
alignb 16
stack:     resb 8192
stack_top:
