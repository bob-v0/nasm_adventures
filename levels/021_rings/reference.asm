; Level 21 — Privilege Rings (reference)

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1
P        equ 1 << 0
W        equ 1 << 1
PS       equ 1 << 7
NX_HIGH  equ 1 << 31
HIGH     equ 0xFFFFFFFF80000000     ; the higher half: virtual HIGH + x = physical x
EFER     equ 0xC0000080
USER     equ 0x400000           ; the user program: a 2 MiB page user mode may use
USER_TOP equ 0x600000           ; (its stack grows down from the top)
U        equ 1 << 2             ; user: in an entry, at every level of the walk
KERNEL_CS equ 0x08
KERNEL_DS equ 0x10
USER_DS  equ 0x18
USER_CS  equ 0x20
TSS_SEL  equ 0x28

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
    mov dword [pml4 + 0 * 8], pdpt_low + P + W + U   ; (U here and below: one
    mov dword [pml4 + 256 * 8], pdpt_low + P + W
    mov dword [pml4 + 256 * 8 + 4], NX_HIGH
    mov dword [pml4 + 511 * 8], pdpt_high + P + W
    mov dword [pdpt_low + 0 * 8], pd + P + W + U     ;  2 MiB page of it is user's)
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
    or dword [pd + 2 * 8], U    ; 0x400000-0x5FFFFF: the user program's page
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
    call silence_pic             ; (the legacy PIC's IRQs would land on the exception vectors)
    ; the game's test: the first module, copied to MODULE and called
    mov ebx, [boot_info]
    mov esi, [rbx + 24]
    mov ecx, [rsi + 4]
    mov esi, [rsi]
    sub ecx, esi
    mov edi, USER
    rep movsb
    ; to ring 3: iretq pops rip, cs, rflags, rsp, ss, so push a frame that says user mode
    push USER_DS | 3                ; ss (RPL 3)
    push USER_TOP                   ; rsp
    push 0x202                      ; rflags: IF on
    push USER_CS | 3                ; cs (RPL 3: the ring to return to)
    push USER                       ; rip
    iretq

; int 0x80 from ring 3: rax = 1 write(rsi, rdx), rax = 60 exit(rdi)
syscall_int:
    cmp rax, 60
    je .exit
    cmp rax, 1
    jne .done
    push rsi
    push rcx
    mov rcx, rdx
    jrcxz .written
.byte:
    lodsb
    call putc
    loop .byte
.written:
    pop rcx
    pop rsi
.done:
    iretq
.exit:
    mov rsi, s_exit
    call puts
    mov rax, rdi
    call decimal
    mov rsi, crlf
    call puts
    cli
    hlt

decimal:
    mov rbx, 10
    xor ecx, ecx
.d:
    xor edx, edx
    div rbx
    push rdx
    inc ecx
    test rax, rax
    jnz .d
.o:
    pop rax
    add al, '0'
    call putc
    loop .o
    ret

; the 8259s: remapped off the exception vectors, and masked (level 34)
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

; ---- the IDT ------------------------------------------------------------------------

init_idt:
    ; the TSS: only IST1 matters here, a stack of its own for #DF
    mov rax, HIGH + stack_top
    mov [tss + 4], rax              ; RSP0: the kernel stack, for interrupts from ring 3
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
    mov ax, TSS_SEL
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
    ; int 0x80: a gate ring 3 may use (DPL 3: type 0xEE)
    mov rax, HIGH + syscall_int
    mov [idt + 0x80 * 16], ax
    mov word [idt + 0x80 * 16 + 2], KERNEL_CS
    mov byte [idt + 0x80 * 16 + 5], 0xEE
    shr rax, 16
    mov [idt + 0x80 * 16 + 6], ax
    shr rax, 16
    mov [idt + 0x80 * 16 + 8], eax
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
    dq 0x0000F20000000000           ; 0x18 user data: DPL 3
    dq 0x0020FA0000000000           ; 0x20 user code: DPL 3, L
gdt_tss:
    dq 0, 0                         ; the TSS (filled in by init_idt)
gdt_end:
gdt_pointer:
    dw gdt_end - gdt - 1
    dq gdt
idt_pointer:
    dw 256 * 16 - 1
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
s_exit:  db "user program exited with status ", 0
digits:  db "0123456789abcdef"
s_0x:    db "0x", 0
crlf:    db 13, 10, 0

section .bss
boot_info: resd 1
alignb 16
idt:       resb 256 * 16
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
