; Level 15 — printk (reference)

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1
P        equ 1 << 0
W        equ 1 << 1
PS       equ 1 << 7
NX_HIGH  equ 1 << 31
HIGH     equ 0xFFFFFFFF80000000     ; the higher half: virtual HIGH + x = physical x
EFER     equ 0xC0000080
MODULE   equ 0x80000

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start
_start:
    mov esp, stack_top
    mov [boot_info], ebx
    ; One PD maps the first 1 GiB, and all three regions share it:
    ;   PML4[0]   -> pdpt_low[0]    -> pd   identity
    ;   PML4[511] -> pdpt_high[510] -> pd   0xFFFFFFFF80000000
    ;   PML4[256] -> pdpt_low[0]    -> pd   0xFFFF800000000000, NX at the PML4 level
    mov dword [pml4 + 0 * 8], pdpt_low + P + W
    mov dword [pml4 + 256 * 8], pdpt_low + P + W
    mov dword [pml4 + 256 * 8 + 4], NX_HIGH
    mov dword [pml4 + 511 * 8], pdpt_high + P + W
    mov dword [pdpt_low + 0 * 8], pd + P + W
    mov dword [pdpt_high + 510 * 8], pd + P + W
    ; the first 2 MiB through a page table, so its first 4 KiB can stay unmapped
    mov dword [pd + 0 * 8], pt + P + W
    mov ecx, 1
.small:
    mov eax, ecx
    shl eax, 12
    or eax, P + W
    mov [pt + ecx * 8], eax
    inc ecx
    cmp ecx, 512
    jb .small
    ; the rest: 2 MiB pages
    mov ecx, 1
.large:
    mov eax, ecx
    shl eax, 21
    or eax, P + W + PS
    mov [pd + ecx * 8], eax
    inc ecx
    cmp ecx, 512
    jb .large
    ; the switch: PAE on, CR3 = the PML4, EFER.LME (and NXE: the direct map uses NX),
    ; then paging on, which (with LME) activates long mode
    mov eax, cr4
    or eax, 1 << 5              ; PAE
    mov cr4, eax
    mov eax, pml4
    mov cr3, eax
    mov ecx, EFER
    rdmsr
    or eax, 1 << 8 | 1 << 11    ; LME, NXE
    wrmsr
    mov eax, cr0
    or eax, 1 << 31             ; PG
    mov cr0, eax
    ; still running 32-bit code ("compatibility mode") until CS is a 64-bit segment
    lgdt [gdt_pointer]
    jmp 0x08:long_mode

bits 64
long_mode:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    xor ax, ax
    mov fs, ax
    mov gs, ax
    mov rax, HIGH + higher_half     ; the same code, through the higher half's mapping
    jmp rax
higher_half:
    mov rsp, HIGH + stack_top
    call init_idt
    ; the game's test: the first module, copied to MODULE and called
    mov ebx, [boot_info]
    mov esi, [rbx + 24]
    mov ecx, [rsi + 4]
    mov esi, [rsi]
    sub ecx, esi
    mov edi, MODULE
    rep movsb
    mov rdi, printk                 ; the game's test: printk and hexdump
    mov rsi, hexdump
    mov rax, MODULE
    call rax
    mov rsi, s_done
    call puts
    cli
    hlt

; ---- printk -------------------------------------------------------------------------

; printk(rdi = format, then the arguments: rsi, rdx, rcx, r8, r9, then on the stack):
; %d %u %x %p %s %c %%, with an optional '-' (left-align), '0' (pad numbers with zeros)
; and a width. rax = the number of characters printed. The C convention.
printk:
    push rbp
    mov rbp, rsp
    push r9                         ; the register arguments, in a row below rbp:
    push r8                         ;   argument k (k < 5) at [rbp - 40 + 8k],
    push rcx                        ;   then the stack ones at [rbp + 16 + 8(k - 5)]
    push rdx
    push rsi
    push rbx
    push r12
    push r13
    push r14
    push r15
    sub rsp, 40                     ; the digits of a number
    mov r12, rdi                    ; the format
    xor r13d, r13d                  ; the next argument
    xor r14d, r14d                  ; characters printed
.next:
    movzx eax, byte [r12]
    inc r12
    test al, al
    jz .done
    cmp al, '%'
    je .spec
    call emit
    jmp .next
.spec:
    xor r15d, r15d                  ; flags: bit 0 '-', bit 1 '0'; width in bits 8+
    cmp byte [r12], '-'
    jne .zero
    or r15d, 1
    inc r12
.zero:
    cmp byte [r12], '0'
    jne .width
    or r15d, 2
    inc r12
.width:
    movzx eax, byte [r12]
    sub eax, '0'
    cmp eax, 9
    ja .conv
    mov ecx, r15d
    shr ecx, 8
    imul ecx, ecx, 10
    add ecx, eax
    shl ecx, 8
    and r15d, 0xFF
    or r15d, ecx
    inc r12
    jmp .width
.conv:
    movzx eax, byte [r12]
    inc r12
    cmp al, '%'
    jne .arg
    call emit
    jmp .next
.arg:
    mov ebx, eax                    ; the conversion
    call next_arg                   ; rax = the argument
    cmp bl, 'c'
    je .char
    cmp bl, 's'
    je .string
    cmp bl, 'p'
    je .pointer
    ; a number: digits backwards into the buffer at rsp
    lea rdi, [rsp + 40]
    xor esi, esi                    ; the sign: 0 or '-'
    mov ecx, 10
    cmp bl, 'x'
    jne .decimal
    mov ecx, 16
    jmp .digits
.decimal:
    cmp bl, 'd'
    jne .digits
    test rax, rax
    jns .digits
    neg rax
    mov esi, '-'
.digits:
    xor edx, edx
    div rcx
    mov dl, [digits + rdx]
    dec rdi
    mov [rdi], dl
    test rax, rax
    jnz .digits
    lea rcx, [rsp + 40]
    sub rcx, rdi                    ; how many digits
    mov rdx, rcx
    test esi, esi
    jz .counted
    inc rdx                         ; (with the sign)
.counted:
    mov eax, r15d
    shr eax, 8                      ; the width
    sub rax, rdx                    ; the padding
    jg .pad
    xor eax, eax
.pad:
    test r15d, 1                    ; left-aligned: text, then spaces
    jnz .left_number
    test r15d, 2
    jnz .zeros
    call spaces
    call sign
    jmp .number_text
.zeros:
    call sign
    push rax
    push rcx
    mov rcx, rax
    jrcxz .zeros_done
.zero_out:
    mov al, '0'
    call emit
    loop .zero_out
.zeros_done:
    pop rcx
    pop rax
    jmp .number_text
.left_number:
    call sign
    push rax
    call text
    pop rax
    call spaces
    jmp .next
.number_text:
    call text
    jmp .next

.char:
    mov [rsp], al
    mov rdi, rsp
    mov ecx, 1
    jmp .padded_text
.string:
    mov rdi, rax
    test rdi, rdi
    jnz .measure
    mov rdi, s_null
.measure:
    xor ecx, ecx
.len:
    cmp byte [rdi + rcx], 0
    je .padded_text
    inc ecx
    jmp .len
.padded_text:                       ; rdi = text, rcx = its length; spaces as the width asks
    mov eax, r15d
    shr eax, 8
    sub rax, rcx
    jg .have_pad
    xor eax, eax
.have_pad:
    xor esi, esi
    test r15d, 1
    jnz .left_text
    call spaces
    call text
    jmp .next
.left_text:
    push rax
    call text
    pop rax
    call spaces
    jmp .next

.pointer:
    mov rdx, rax
    mov al, '0'
    call emit
    mov al, 'x'
    call emit
    mov ecx, 16
.hex:
    rol rdx, 4
    mov eax, edx
    and eax, 15
    mov al, [digits + rax]
    call emit
    loop .hex
    jmp .next

.done:
    mov rax, r14
    add rsp, 40
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    mov rsp, rbp
    pop rbp
    ret

; (printk's helpers: they use its registers and frame)
next_arg:                           ; rax = argument r13, then r13 + 1
    cmp r13, 5
    jae .stack
    mov rax, [rbp - 40 + r13 * 8]
    inc r13
    ret
.stack:
    mov rax, [rbp + 16 + r13 * 8 - 40]
    inc r13
    ret
emit:                               ; al: print it, count it
    call putc
    inc r14
    ret
spaces:                             ; rax spaces
    push rcx
    push rax
    mov rcx, rax
    jrcxz .none
.space:
    mov al, ' '
    call emit
    loop .space
.none:
    pop rax
    pop rcx
    ret
sign:                               ; esi: '-' or 0
    test esi, esi
    jz .none
    push rax
    mov eax, esi
    call emit
    pop rax
.none:
    ret
text:                               ; rdi = text, rcx = length
    push rcx
    push rdi
    jrcxz .none
.char:
    mov al, [rdi]
    inc rdi
    call emit
    loop .char
.none:
    pop rdi
    pop rcx
    ret

; hexdump(rdi = address, rsi = length): like `hexdump -C`, 16 bytes a line
hexdump:
    push rbx
    push r12
    push r13
    push r14
    mov r12, rdi                    ; the line's address
    mov r13, rsi                    ; bytes left
.line:
    test r13, r13
    jz .out
    mov rax, r12
    call hex64_bare
    mov al, ' '
    call putc
    call putc
    xor ebx, ebx
.byte:
    cmp rbx, r13
    jae .blank
    movzx eax, byte [r12 + rbx]
    push rax
    shr eax, 4
    mov al, [digits + rax]
    call putc
    pop rax
    and eax, 15
    mov al, [digits + rax]
    call putc
    jmp .sep
.blank:
    mov al, ' '
    call putc
    call putc
.sep:
    mov al, ' '
    cmp ebx, 15
    je .ascii
    call putc
    cmp ebx, 7
    jne .next_byte
    call putc
.next_byte:
    inc ebx
    jmp .byte
.ascii:
    call putc
    call putc
    mov al, '|'
    call putc
    xor ebx, ebx
.char:
    cmp ebx, 16
    jae .end_line
    cmp rbx, r13
    jae .end_line
    mov al, [r12 + rbx]
    cmp al, 32
    jb .dot
    cmp al, 127
    jb .plain
.dot:
    mov al, '.'
.plain:
    call putc
    inc ebx
    jmp .char
.end_line:
    mov al, '|'
    call putc
    mov rsi, crlf
    call puts
    add r12, 16
    sub r13, 16
    jbe .out
    jmp .line
.out:
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

hex64_bare:                         ; rax as 16 hex digits
    push rcx
    push rdx
    mov rdx, rax
    mov ecx, 16
.d:
    rol rdx, 4
    mov eax, edx
    and eax, 15
    mov al, [digits + rax]
    call putc
    loop .d
    pop rdx
    pop rcx
    ret

; ---- the IDT ------------------------------------------------------------------------

init_idt:
    ; the TSS: only IST1 matters here, a stack of its own for #DF
    mov rax, HIGH + df_stack_top
    mov [tss + 36], rax             ; IST1
    mov word [tss + 102], 104       ; I/O map base: none
    ; its descriptor: 16 bytes in the GDT
    mov rax, tss
    mov word [gdt_tss], 103         ; limit
    mov [gdt_tss + 2], ax           ; base 0-15
    shr rax, 16
    mov [gdt_tss + 4], al           ; base 16-23
    mov byte [gdt_tss + 5], 0x89    ; present, 64-bit TSS (available)
    mov [gdt_tss + 7], ah           ; base 24-31
    shr rax, 16
    mov [gdt_tss + 8], eax          ; base 32-63
    lgdt [gdt_pointer]
    mov ax, 0x18
    ltr ax
    ; 32 gates: stub n is at stubs + n * STUB
    xor ecx, ecx
.gate:
    mov rax, HIGH + stubs
    imul rdx, rcx, STUB
    add rax, rdx
    shl rcx, 4                      ; 16 bytes a gate
    mov [idt + rcx], ax             ; offset 0-15
    mov word [idt + rcx + 2], 0x08  ; code segment
    mov byte [idt + rcx + 4], 0     ; IST: none...
    mov byte [idt + rcx + 5], 0x8E  ; present, ring 0, interrupt gate
    shr rax, 16
    mov [idt + rcx + 6], ax         ; offset 16-31
    shr rax, 16
    mov [idt + rcx + 8], eax        ; offset 32-63
    shr rcx, 4
    inc ecx
    cmp ecx, 32
    jb .gate
    mov byte [idt + 8 * 16 + 4], 1  ; ...except #DF: IST1
    lidt [idt_pointer]
    ret

; one stub per vector, each STUB bytes: push a 0 where the CPU pushes no error code,
; then the vector, then the common handler
STUB equ 16
%macro stub 1
    align STUB
%if %1 = 8 || (%1 >= 10 && %1 <= 14) || %1 = 17 || %1 = 21 || %1 = 29 || %1 = 30
    nop
    nop
%else
    push 0
%endif
    push %1
    jmp exception
%endmacro
align STUB
stubs:
%assign n 0
%rep 32
    stub n
%assign n n + 1
%endrep

; the frame: [rsp] vector, [rsp+8] error code, [rsp+16] rip, cs, rflags, rsp, ss
exception:
    push rax
    push rcx
    push rdx
    push rsi
    mov rcx, [rsp + 32]             ; the vector
    lea rsi, [names + rcx * 4]
    call puts
    mov rsi, s_at
    call puts
    mov rax, [rsp + 48]
    call hex64
    mov rcx, [rsp + 32]
    bt [has_error], ecx
    jnc .no_error
    mov rsi, s_error
    call puts
    mov rax, [rsp + 40]
    call hex64
.no_error:
    mov rcx, [rsp + 32]             ; (hex64 used rcx)
    cmp rcx, 14
    jne .no_cr2
    mov rsi, s_cr2
    call puts
    mov rax, cr2
    call hex64
.no_cr2:
    mov rsi, crlf
    call puts
    cmp qword [rsp + 32], 3                      ; #BP is a trap: carry on after the int3
    jne .stop
    pop rsi
    pop rdx
    pop rcx
    pop rax
    add rsp, 16                     ; the vector and the error code
    iretq
.stop:
    cli
    hlt
    jmp .stop

hex64:                              ; rax as 0x + 16 hex digits
    push rax
    mov rsi, s_0x
    call puts
    pop rdx
    mov ecx, 16
.digit:
    rol rdx, 4
    mov eax, edx
    and eax, 15
    mov al, [digits + rax]
    call putc
    loop .digit
    ret

putc:
    push rdx
    push rax
    mov dx, 0x3FD
.ready:
    in al, dx
    test al, 0x20
    jz .ready
    pop rax
    mov dx, 0x3F8
    out dx, al
    pop rdx
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
    dq 0x00209A0000000000           ; code: present, ring 0, L (64-bit)
    dq 0x0000920000000000           ; data: present, writable
gdt_tss:
    dq 0, 0                         ; the TSS (filled in by init_idt)
gdt_end:
gdt_pointer:
    dw gdt_end - gdt - 1
    dq gdt
idt_pointer:
    dw 32 * 16 - 1
    dq idt
has_error:  dd 1 << 8 | 1 << 10 | 1 << 11 | 1 << 12 | 1 << 13 | 1 << 14 | 1 << 17 | 1 << 21 | 1 << 29 | 1 << 30
names:                              ; 4 bytes each
    db "#DE", 0, "#DB", 0, "NMI", 0, "#BP", 0, "#OF", 0, "#BR", 0, "#UD", 0, "#NM", 0
    db "#DF", 0, "#CS", 0, "#TS", 0, "#NP", 0, "#SS", 0, "#GP", 0, "#PF", 0, "#15", 0
    db "#MF", 0, "#AC", 0, "#MC", 0, "#XM", 0, "#VE", 0, "#CP", 0, "#22", 0, "#23", 0
    db "#24", 0, "#25", 0, "#26", 0, "#27", 0, "#HV", 0, "#VC", 0, "#SX", 0, "#31", 0
s_at:    db " at ", 0
s_error: db ", error code ", 0
s_cr2:   db ", cr2 ", 0
s_done:  db "done", 13, 10, 0
s_null:  db "(null)", 0
digits:  db "0123456789abcdef"
s_0x:    db "0x", 0
crlf:    db 13, 10, 0

section .bss
boot_info: resd 1
alignb 16
idt:       resb 32 * 16
tss:       resb 104
alignb 16
df_stack:  resb 4096
df_stack_top:
alignb 4096
pml4:      resq 512
pdpt_low:  resq 512
pdpt_high: resq 512
pd:        resq 512
pt:        resq 512
alignb 16
stack:     resb 8192
stack_top:
