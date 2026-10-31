; Level 53 — JIT (reference)
;
; Template JIT: each bytecode op becomes a fixed piece of machine code (copied from
; templates assembled into .rodata), with stack checks in front. Code size per op doesn't
; depend on jump targets (rel32 everywhere), so pass 1 records where each op's code
; starts and pass 2 emits everything again with the JNZ targets known.
;
; Generated code: rdi = the VM stack (32 qwords), r9 = depth. It returns like the
; level 150 VM: rax = top (or 0), rdx = status, rcx = depth.

global ring_run

PROT_READ  equ 1
PROT_WRITE equ 2
PROT_EXEC  equ 4
JIT_SIZE   equ 8192

section .rodata
stubs:                          ; at the start of the generated code
s_halt:
    xor eax, eax
    test r9, r9
    jz .empty
    mov rax, [rdi + r9*8 - 8]
.empty:
    xor edx, edx
    mov rcx, r9
    ret
s_bad:
    mov edx, 1
    jmp s_fail
s_under:
    mov edx, 2
    jmp s_fail
s_over:
    mov edx, 3
s_fail:
    xor eax, eax
    mov rcx, r9
    ret
s_entry:
    xor r9d, r9d                ; depth 0
stubs_end:

b_add:  mov rax, [rdi + r9*8 - 8]
        add [rdi + r9*8 - 16], rax
        dec r9
b_sub:  mov rax, [rdi + r9*8 - 8]
        sub [rdi + r9*8 - 16], rax
        dec r9
b_mul:  mov rax, [rdi + r9*8 - 16]
        imul rax, [rdi + r9*8 - 8]
        mov [rdi + r9*8 - 16], rax
        dec r9
b_dup:  mov rax, [rdi + r9*8 - 8]
        mov [rdi + r9*8], rax
        inc r9
b_swap: mov rax, [rdi + r9*8 - 8]
        mov rdx, [rdi + r9*8 - 16]
        mov [rdi + r9*8 - 8], rdx
        mov [rdi + r9*8 - 16], rax
b_drop: dec r9
b_over: mov rax, [rdi + r9*8 - 16]
        mov [rdi + r9*8], rax
        inc r9
b_rot:  mov rax, [rdi + r9*8 - 24]      ; a b c -> b c a
        mov rdx, [rdi + r9*8 - 16]
        mov [rdi + r9*8 - 24], rdx
        mov rdx, [rdi + r9*8 - 8]
        mov [rdi + r9*8 - 16], rdx
        mov [rdi + r9*8 - 8], rax
b_jnz:  dec r9
        cmp qword [rdi + r9*8], 0       ; (then: jne rel32)
b_push: mov qword [rdi + r9*8], strict dword 0   ; (the last 4 bytes: the value)
b_push_inc:
        inc r9
b_end:

; per opcode: template, length, values needed, grows the stack, kind (0 plain, 1 push,
; 2 jnz, 3 halt)
ops:
    dq 0, 0
    db 0, 0, 3, 0, 0, 0, 0, 0               ; HALT
    dq b_push, b_push_inc - b_push
    db 0, 1, 1, 0, 0, 0, 0, 0               ; PUSH
    dq b_add, b_sub - b_add
    db 2, 0, 0, 0, 0, 0, 0, 0               ; ADD
    dq b_sub, b_mul - b_sub
    db 2, 0, 0, 0, 0, 0, 0, 0               ; SUB
    dq b_mul, b_dup - b_mul
    db 2, 0, 0, 0, 0, 0, 0, 0               ; MUL
    dq b_dup, b_swap - b_dup
    db 1, 1, 0, 0, 0, 0, 0, 0               ; DUP
    dq b_swap, b_drop - b_swap
    db 2, 0, 0, 0, 0, 0, 0, 0               ; SWAP
    dq b_drop, b_over - b_drop
    db 1, 0, 0, 0, 0, 0, 0, 0               ; DROP
    dq b_over, b_rot - b_over
    db 2, 1, 0, 0, 0, 0, 0, 0               ; OVER
    dq b_rot, b_jnz - b_rot
    db 3, 0, 0, 0, 0, 0, 0, 0               ; ROT
    dq b_jnz, b_push - b_jnz
    db 1, 0, 2, 0, 0, 0, 0, 0               ; JNZ
OP_SIZE equ 24

section .text
ring_run:                       ; rdi = code (64 bytes)
    push rbx
    push rbp
    push r12
    push r13
    push r14
    push r15
    sub rsp, 64*4 + 32*8 + 8    ; code offsets per pc; the VM stack
    mov rbx, rdi
    mov eax, 9                  ; mmap(0, JIT_SIZE, READ | WRITE, PRIVATE | ANONYMOUS)
    xor edi, edi
    mov esi, JIT_SIZE
    mov edx, PROT_READ | PROT_WRITE
    mov r10d, 0x22
    mov r8, -1
    xor r9d, r9d
    syscall
    mov r12, rax                ; the code buffer
    mov ebp, 2
.pass:
    call compile
    dec ebp
    jnz .pass
    mov eax, 10                 ; mprotect(buffer, JIT_SIZE, READ | EXEC): W^X
    mov rdi, r12
    mov esi, JIT_SIZE
    mov edx, PROT_READ | PROT_EXEC
    syscall
    lea rdi, [rsp + 64*4]       ; the VM stack
    lea rax, [r12 + s_entry - stubs]
    call rax                    ; run it
    mov rbx, rax
    mov rbp, rdx
    mov r13, rcx
    mov eax, 11                 ; munmap
    mov rdi, r12
    mov esi, JIT_SIZE
    syscall
    mov rax, rbx
    mov rdx, rbp
    mov rcx, r13
    add rsp, 64*4 + 32*8 + 8
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbp
    pop rbx
    ret

; one pass over the bytecode: rbx = code, r12 = buffer, [rsp+8] = offsets
compile:
    lea r15, [rsp + 8]          ; (above our return address)
    mov r13, r12
    lea rsi, [rel stubs]
    mov ecx, stubs_end - stubs
    call emit
    xor r14d, r14d              ; pc
.op:
    cmp r14d, 64
    jae .done
    mov eax, r13d
    sub eax, r12d
    mov [r15 + r14*4], eax      ; this op's code starts here
    movzx eax, byte [rbx + r14]
    inc r14d
    cmp eax, 10
    ja .bad
    imul eax, eax, OP_SIZE
    lea rdx, [rel ops]
    add rdx, rax                ; the op's entry
    movzx eax, byte [rdx + 16]  ; values needed
    test eax, eax
    jz .no_under
    mov byte [r13], 0x49        ; cmp r9, imm8
    mov word [r13 + 1], 0xF983
    mov [r13 + 3], al
    mov word [r13 + 4], 0x820F  ; jb rel32 -> s_under
    add r13, 6
    mov eax, s_under - stubs
    call emit_rel32
.no_under:
    cmp byte [rdx + 17], 0      ; grows?
    je .no_over
    mov dword [r13], 0x20F98349 ; cmp r9, 32
    mov word [r13 + 4], 0x830F  ; jae rel32 -> s_over
    add r13, 6
    mov eax, s_over - stubs
    call emit_rel32
.no_over:
    movzx eax, byte [rdx + 18]  ; kind
    cmp eax, 3
    je .halt
    mov rsi, [rdx]
    mov rcx, [rdx + 8]
    push rax
    call emit
    pop rax
    cmp eax, 1
    je .push
    cmp eax, 2
    je .jnz
    jmp .op
.push:
    movsx eax, byte [rbx + r14] ; the value, sign-extended
    inc r14d
    mov [r13 - 4], eax
    lea rsi, [rel b_push_inc]
    mov ecx, b_end - b_push_inc
    call emit
    jmp .op
.jnz:
    movsx eax, byte [rbx + r14] ; the offset
    inc r14d
    add eax, r14d               ; the target pc
    and eax, 63                 ; (tests only jump to the start of an op)
    mov eax, [r15 + rax*4]      ; its code (pass 2: known; pass 1: anything)
    mov word [r13], 0x850F      ; jne rel32
    add r13, 2
    call emit_rel32
    jmp .op
.halt:
    mov eax, s_halt - stubs
    jmp .jump
.bad:
    mov eax, s_bad - stubs
.jump:
    mov byte [r13], 0xE9        ; jmp rel32
    inc r13
    call emit_rel32
    jmp .op
.done:
    ret

emit:                           ; copy rcx bytes from rsi to r13
    test rcx, rcx
    jz .done
    mov al, [rsi]
    mov [r13], al
    inc rsi
    inc r13
    dec rcx
    jmp emit
.done:
    ret

emit_rel32:                     ; eax = a target offset in the buffer
    mov ecx, r13d
    sub ecx, r12d
    add ecx, 4                  ; the end of this rel32
    sub eax, ecx
    mov [r13], eax
    add r13, 4
    ret
