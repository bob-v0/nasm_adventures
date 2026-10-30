; Level 115 — Position Independence (reference)
default rel                     ; every [label] is RIP-relative

extern puts
global main

section .text
main:                           ; main(argc, argv)
    push rbx
    push r12
    push r13                    ; three pushes: rsp is 16-byte aligned again
    mov r12d, edi
    mov r13, rsi
    mov ebx, 1
.next:
    cmp ebx, r12d
    jge .done
    mov rax, [r13 + rbx*8]      ; argv[i]
    movzx eax, byte [rax]
    sub eax, '0'
    lea rcx, [days]             ; no absolute addresses: lea, then index
    mov rdi, [rcx + rax*8]
    call puts wrt ..plt         ; through the PLT: libc is somewhere else
    mov rax, [r13 + rbx*8]      ; (rax didn't survive the call)
    movzx eax, byte [rax]
    sub eax, '0'
    lea rcx, [kinds]            ; offsets, not addresses: no relocation at all
    movsxd rdx, [rcx + rax*4]
    add rdx, rcx
    jmp rdx
.weekday:
    lea rdi, [work]
    jmp .print
.weekend:
    lea rdi, [rest]
.print:
    call puts wrt ..plt
    inc ebx
    jmp .next
.done:
    xor eax, eax
    pop r13
    pop r12
    pop rbx
    ret

section .rodata
kinds: dd main.weekday - kinds, main.weekday - kinds, main.weekday - kinds, main.weekday - kinds
       dd main.weekday - kinds, main.weekend - kinds, main.weekend - kinds
mon: db "Monday", 0
tue: db "Tuesday", 0
wed: db "Wednesday", 0
thu: db "Thursday", 0
fri: db "Friday", 0
sat: db "Saturday", 0
sun: db "Sunday", 0
work: db "  work", 0
rest: db "  rest", 0

section .data                   ; pointers: the loader fills them in (R_X86_64_RELATIVE)
days: dq mon, tue, wed, thu, fri, sat, sun
