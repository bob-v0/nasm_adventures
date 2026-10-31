; Level 30 — The sti;hlt Race (reference)
;! witness delay = 700
;
; A driver's main loop, in miniature: it starts an I/O request, then sleeps until the
; device's completion interrupt arrives, 50 times. (The "device" is the APIC timer in
; one-shot mode: it interrupts once, `delay` timer ticks after the request, plus 1 more tick
; for each request, from the command line "delay=N".) At the end it says
;     50 requests completed
;
; With some delays, the kernel never finishes: it sleeps forever, after an interrupt
; that did arrive.
;
; 1. Find a delay that hangs it:   ;! witness delay = N
; 2. Fix it.

bits 32

MB_FLAGS  equ 1 << 0 | 1 << 1
REQUESTS  equ 50
APIC_EOI  equ 0xB0
APIC_SVR  equ 0xF0
LVT_TIMER equ 0x320
INITIAL   equ 0x380
DIVIDE    equ 0x3E0

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
    mov eax, completed
    mov ecx, 0x40
    call set_gate
    mov eax, spurious
    mov ecx, 0xFF
    call set_gate
    lidt [idt_pointer]
    call silence_pic
    call read_delay
    mov [delay], eax
    mov ecx, 0x1B
    rdmsr
    and eax, 0xFFFFF000
    mov [apic], eax
    mov dword [eax + APIC_SVR], 0x1FF
    mov dword [eax + DIVIDE], 0xB       ; ÷1
    mov dword [eax + LVT_TIMER], 0x40   ; one-shot, vector 0x40
    sti
    xor ebx, ebx                ; requests completed
request:
    mov byte [done], 0
    mov eax, [delay]            ; start the I/O: the completion comes delay + n cycles later
    add eax, ebx
    mov edx, [apic]
    mov [edx + INITIAL], eax
sleep:                           ; sleep until it's done
    cli                         ; no interrupt between the check and the sleep...
    cmp byte [done], 0
    jne .finished
    call progress               ; show which request we're waiting for
    sti                         ; ...because sti takes effect after the NEXT instruction:
    hlt                         ; an interrupt pending now wakes the hlt, not the code before it
    jmp sleep
.finished:
    sti
    inc ebx
    cmp ebx, REQUESTS
    jb request
    cli
    mov eax, ebx
    call decimal
    mov esi, s_done
    call puts
    hlt

completed:                      ; the device's completion interrupt
    mov byte [done], 1
    push eax
    mov eax, [apic]
    mov dword [eax + APIC_EOI], 0
    pop eax
    iret

spurious:
    iret

progress:                       ; "waiting for request N" on the screen's top line
    push eax
    push ecx
    push edx
    push esi
    push edi
    mov edi, 0xB8000
    mov esi, s_waiting
.text:
    lodsb
    test al, al
    jz .number
    mov ah, 0x07
    stosw
    jmp .text
.number:
    lea eax, [ebx + 1]
    mov ecx, 10
    xor edx, edx
    div ecx                     ; eax = tens, edx = ones
    add al, '0'
    mov ah, 0x07
    stosw
    lea eax, [edx + '0']
    mov ah, 0x07
    stosw
    pop edi
    pop esi
    pop edx
    pop ecx
    pop eax
    ret

read_delay:                     ; "delay=N" in the multiboot command line -> eax = N
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
    mov eax, 5000
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
.ready:
    in al, dx
    test al, 0x20
    jz .ready
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
s_waiting: db "waiting for request ", 0
s_done: db " requests completed", 13, 10, 0

section .bss
alignb 4
apic:      resd 1
boot_info: resd 1
delay:     resd 1
done:      resb 1
alignb 8
idt:       resq 256
alignb 16
stack:     resb 8192
stack_top:
