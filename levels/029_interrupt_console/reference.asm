; Level 29 — Interrupt-Driven Console (reference)

bits 32

MB_FLAGS     equ 1 << 0 | 1 << 1
APIC_EOI     equ 0xB0
APIC_SVR     equ 0xF0
LVT_TIMER    equ 0x320
INITIAL      equ 0x380
CURRENT      equ 0x390
DIVIDE       equ 0x3E0
IOAPIC       equ 0xFEC00000
TIMER_VECTOR equ 0x40
KBD_VECTOR   equ 0x41
COM2_VECTOR  equ 0x43
COM1         equ 0x3F8
COM2         equ 0x2F8
LINE_MAX     equ 60

; a line editor: its text, its length, and whether it has closed ("bye")
struc editor
    .text:   resb LINE_MAX
    .length: resd 1
    .name:   resd 1             ; "kbd: " or "com2: "
    .closed: resd 1
endstruc

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
    mov eax, timer
    mov ecx, TIMER_VECTOR
    call set_gate
    mov eax, keyboard
    mov ecx, KBD_VECTOR
    call set_gate
    mov eax, serial
    mov ecx, COM2_VECTOR
    call set_gate
    mov eax, spurious
    mov ecx, 0xFF
    call set_gate
    lidt [idt_pointer]
    call silence_pic
    mov dword [kbd + editor.name], s_kbd
    mov dword [com + editor.name], s_com
    ; the Local APIC, and its timer at 100 Hz (level 33)
    mov ecx, 0x1B
    rdmsr
    and eax, 0xFFFFF000
    mov [apic], eax
    mov ebx, eax
    mov dword [ebx + APIC_SVR], 0x1FF
    mov dword [ebx + DIVIDE], 0x3
    in al, 0x61
    and al, 0xFC
    or al, 1
    out 0x61, al
    mov al, 0xB0
    out 0x43, al
    mov ax, 11932
    out 0x42, al
    mov al, ah
    out 0x42, al
    mov dword [ebx + INITIAL], 0xFFFFFFFF
.pit:
    in al, 0x61
    test al, 0x20
    jz .pit
    mov eax, 0xFFFFFFFF
    sub eax, [ebx + CURRENT]
    mov dword [ebx + LVT_TIMER], 1 << 17 | TIMER_VECTOR
    mov [ebx + INITIAL], eax
    ; COM2: 8N1, received-data interrupt on
    mov dx, COM2 + 3
    mov al, 0x03
    out dx, al
    mov dx, COM2 + 4
    mov al, 0x08                ; OUT2: lets the UART's interrupt out
    out dx, al
    mov dx, COM2 + 1
    mov al, 0x01
    out dx, al
    ; the I/O APIC: pin 1 (keyboard) and pin 3 (COM2) to their vectors, CPU 0 (level 32)
    mov dword [IOAPIC], 0x12
    mov dword [IOAPIC + 0x10], KBD_VECTOR
    mov dword [IOAPIC], 0x13
    mov dword [IOAPIC + 0x10], 0
    mov dword [IOAPIC], 0x16
    mov dword [IOAPIC + 0x10], COM2_VECTOR
    mov dword [IOAPIC], 0x17
    mov dword [IOAPIC + 0x10], 0
    mov esi, s_ready
    call puts
    sti

; The handlers only queue what arrived: (source, byte) pairs in one ring buffer. All the
; editing and printing happens here, with interrupts on.
main:
    cli                         ; check and sleep with no gap (level 30)
    mov eax, [tail]
    cmp eax, [head]
    jne .take
    mov eax, [kbd + editor.closed]
    and eax, [com + editor.closed]
    jnz .bye
    sti
    hlt
    jmp main
.take:
    and eax, QUEUE - 1
    movzx ecx, byte [queue_source + eax]
    movzx eax, byte [queue_byte + eax]
    inc dword [tail]
    sti
    test ecx, ecx
    jnz .from_com
    call scancode               ; keyboard: scancode -> character (0: none)
    test al, al
    jz main
    mov edi, kbd
    call edit
    jmp main
.from_com:
    cmp al, 0x7F                ; DEL, as terminals send for backspace
    jne .c1
    mov al, 8
.c1:
    cmp al, 13
    je .c2
    cmp al, 8
    je .c2
    cmp al, ' '
    jb main
    cmp al, '~'
    ja main
.c2:
    mov edi, com
    call edit
    jmp main
.bye:
    mov esi, s_bye
    call puts
    hlt                         ; (interrupts are off)

scancode:                       ; al = set 1 scancode -> al = character, 13, 8, or 0
    test al, 0x80               ; releases
    jnz .none
    cmp al, 0x1C
    je .enter
    cmp al, 0x0E
    je .back
    cmp al, 0x39
    ja .none
    movzx eax, al
    mov al, [keymap + eax]
    ret
.enter:
    mov al, 13
    ret
.back:
    mov al, 8
    ret
.none:
    xor eax, eax
    ret

edit:                           ; edi = editor, al = character, 8 (backspace) or 13 (enter)
    cmp dword [edi + editor.closed], 0
    jne .done
    mov ecx, [edi + editor.length]
    cmp al, 13
    je .enter
    cmp al, 8
    je .back
    cmp ecx, LINE_MAX
    jae .done
    mov [edi + editor.text + ecx], al
    inc dword [edi + editor.length]
.done:
    ret
.back:
    test ecx, ecx
    jz .done
    dec dword [edi + editor.length]
    ret
.enter:
    mov esi, [edi + editor.name]
    call puts
    lea esi, [edi + editor.text]
    jecxz .newline
.out:
    lodsb
    call putc
    loop .out
.newline:
    mov esi, crlf
    call puts
    cmp dword [edi + editor.length], 3
    jne .open
    cmp word [edi + editor.text], 'by'
    jne .open
    cmp byte [edi + editor.text + 2], 'e'
    jne .open
    mov dword [edi + editor.closed], 1  ; "bye": this source is done
.open:
    mov dword [edi + editor.length], 0
    ret

; ---- interrupt handlers -------------------------------------------------------------

timer:
    inc dword [ticks]
    push eax
    mov eax, [apic]
    mov dword [eax + APIC_EOI], 0
    pop eax
    iret

keyboard:
    push eax
    push ecx
    in al, 0x60
    xor ecx, ecx
    call enqueue
    pop ecx
    pop eax
    jmp eoi_iret

serial:
    push eax
    push ecx
    push edx
.more:
    mov dx, COM2 + 5
    in al, dx
    test al, 1                  ; data ready? (take all of it)
    jz .end
    mov dx, COM2
    in al, dx
    mov ecx, 1
    call enqueue
    jmp .more
.end:
    pop edx
    pop ecx
    pop eax
    jmp eoi_iret

enqueue:                        ; al = byte, ecx = source (in a handler: interrupts are off)
    push ebx
    mov ebx, [head]
    sub ebx, [tail]
    cmp ebx, QUEUE
    jae .full
    mov ebx, [head]
    and ebx, QUEUE - 1
    mov [queue_byte + ebx], al
    mov [queue_source + ebx], cl
    inc dword [head]            ; publish it after it's written
.full:
    pop ebx
    ret

eoi_iret:
    push eax
    mov eax, [apic]
    mov dword [eax + APIC_EOI], 0
    pop eax
    iret

spurious:
    iret

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

QUEUE equ 64

section .bss
alignb 4
apic:         resd 1
ticks:        resd 1
head:         resd 1
tail:         resd 1
queue_byte:   resb QUEUE
queue_source: resb QUEUE
alignb 4
kbd:          resb editor_size
alignb 4
com:          resb editor_size
alignb 8
idt:          resq 256
alignb 16
stack:        resb 8192
stack_top:
