; Level 53 — JIT
;
; ring_run(code): run the 64-byte bytecode program at code (level 150's stack machine:
; the table is in the brief) and return rax = the top of the stack (0 if empty),
; rdx = the status (0 halt, 1 invalid opcode, 2 underflow, 3 overflow), rcx = the depth.
;
; This works: it's an interpreter, at 11 to 27 cycles per op. The budget is 5.
; Compile the program to machine code in memory you mmap, make it executable with
; mprotect (and never writable and executable at the same time), and call it.

global ring_run

section .rodata
align 8
table: dq op_halt, op_push, op_add, op_sub, op_mul, op_dup, op_swap, op_drop, op_over, op_rot, op_jnz
need:  db 0, 0, 2, 2, 2, 1, 2, 1, 2, 3, 1
grow:  db 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0

section .text
ring_run:                       ; rdi = code
    sub rsp, 32*8 + 8           ; the VM stack
    xor esi, esi                ; pc
    xor ecx, ecx                ; depth
next:
    movzx eax, byte [rdi + rsi]
    inc esi
    cmp eax, 10
    ja .bad
    lea rdx, [rel need]
    movzx edx, byte [rdx + rax]
    cmp ecx, edx
    jb .under
    lea rdx, [rel grow]
    movzx edx, byte [rdx + rax]
    add edx, ecx
    cmp edx, 32
    ja .over
    lea rdx, [rel table]
    jmp [rdx + rax*8]           ; dispatch: an indirect jump per op
.bad:
    mov edx, 1
    jmp fail
.under:
    mov edx, 2
    jmp fail
.over:
    mov edx, 3
fail:
    xor eax, eax
    add rsp, 32*8 + 8
    ret

op_halt:
    xor eax, eax
    test ecx, ecx
    jz .empty
    mov rax, [rsp + rcx*8 - 8]
.empty:
    xor edx, edx
    add rsp, 32*8 + 8
    ret
op_push:
    movsx rax, byte [rdi + rsi]
    inc esi
    mov [rsp + rcx*8], rax
    inc ecx
    jmp next
op_add:
    mov rax, [rsp + rcx*8 - 8]
    add [rsp + rcx*8 - 16], rax
    dec ecx
    jmp next
op_sub:
    mov rax, [rsp + rcx*8 - 8]
    sub [rsp + rcx*8 - 16], rax
    dec ecx
    jmp next
op_mul:
    mov rax, [rsp + rcx*8 - 16]
    imul rax, [rsp + rcx*8 - 8]
    mov [rsp + rcx*8 - 16], rax
    dec ecx
    jmp next
op_dup:
    mov rax, [rsp + rcx*8 - 8]
    mov [rsp + rcx*8], rax
    inc ecx
    jmp next
op_swap:
    mov rax, [rsp + rcx*8 - 8]
    mov rdx, [rsp + rcx*8 - 16]
    mov [rsp + rcx*8 - 8], rdx
    mov [rsp + rcx*8 - 16], rax
    jmp next
op_drop:
    dec ecx
    jmp next
op_over:
    mov rax, [rsp + rcx*8 - 16]
    mov [rsp + rcx*8], rax
    inc ecx
    jmp next
op_rot:
    mov rax, [rsp + rcx*8 - 24]
    mov rdx, [rsp + rcx*8 - 16]
    mov [rsp + rcx*8 - 24], rdx
    mov rdx, [rsp + rcx*8 - 8]
    mov [rsp + rcx*8 - 16], rdx
    mov [rsp + rcx*8 - 8], rax
    jmp next
op_jnz:
    movsx rax, byte [rdi + rsi]
    inc esi
    dec ecx
    cmp qword [rsp + rcx*8], 0
    je next
    add esi, eax
    jmp next
