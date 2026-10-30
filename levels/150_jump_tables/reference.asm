; State: r8 = pc (index into code), rcx = depth, vstack[rcx-1] = top.
    xor r8d, r8d
    xor ecx, ecx
next:
    movzx eax, byte [code + r8]
    inc r8
    cmp eax, 10
    ja bad_opcode                   ; bounds check before the table lookup
    jmp [table + rax*8]

op_halt:
    xor eax, eax
    test rcx, rcx
    jz .empty
    mov rax, [vstack + rcx*8 - 8]
.empty:
    xor ebx, ebx
    jmp done
op_push:
    cmp rcx, 32
    jae overflow
    movsx rax, byte [code + r8]
    inc r8
    mov [vstack + rcx*8], rax
    inc rcx
    jmp next
op_add:
    cmp rcx, 2
    jb underflow
    mov rax, [vstack + rcx*8 - 8]
    add [vstack + rcx*8 - 16], rax
    dec rcx
    jmp next
op_sub:
    cmp rcx, 2
    jb underflow
    mov rax, [vstack + rcx*8 - 8]
    sub [vstack + rcx*8 - 16], rax
    dec rcx
    jmp next
op_mul:
    cmp rcx, 2
    jb underflow
    mov rax, [vstack + rcx*8 - 16]
    imul rax, [vstack + rcx*8 - 8]
    mov [vstack + rcx*8 - 16], rax
    dec rcx
    jmp next
op_dup:
    cmp rcx, 1
    jb underflow
    cmp rcx, 32
    jae overflow
    mov rax, [vstack + rcx*8 - 8]
    mov [vstack + rcx*8], rax
    inc rcx
    jmp next
op_swap:
    cmp rcx, 2
    jb underflow
    mov rax, [vstack + rcx*8 - 8]
    mov rdx, [vstack + rcx*8 - 16]
    mov [vstack + rcx*8 - 16], rax
    mov [vstack + rcx*8 - 8], rdx
    jmp next
op_drop:
    cmp rcx, 1
    jb underflow
    dec rcx
    jmp next
op_over:
    cmp rcx, 2
    jb underflow
    cmp rcx, 32
    jae overflow
    mov rax, [vstack + rcx*8 - 16]
    mov [vstack + rcx*8], rax
    inc rcx
    jmp next
op_rot:                             ; a b c -> b c a
    cmp rcx, 3
    jb underflow
    mov rax, [vstack + rcx*8 - 24]  ; a
    mov rdx, [vstack + rcx*8 - 16]  ; b
    mov rsi, [vstack + rcx*8 - 8]   ; c
    mov [vstack + rcx*8 - 24], rdx
    mov [vstack + rcx*8 - 16], rsi
    mov [vstack + rcx*8 - 8], rax
    jmp next
op_jnz:
    cmp rcx, 1
    jb underflow
    movsx rdx, byte [code + r8]
    inc r8                          ; offsets count from the next instruction
    dec rcx
    cmp qword [vstack + rcx*8], 0
    je next
    add r8, rdx
    jmp next

bad_opcode:
    mov ebx, 1
    jmp fail
underflow:
    mov ebx, 2
    jmp fail
overflow:
    mov ebx, 3
fail:
    xor eax, eax
done:

section .data
table: dq op_halt, op_push, op_add, op_sub, op_mul, op_dup, op_swap, op_drop
       dq op_over, op_rot, op_jnz
