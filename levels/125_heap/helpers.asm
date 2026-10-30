; Provided by level 125: a workload for your allocator.
;   ring_workload(): runs `nops` operations from `ops` (3 qwords each: op, slot, size)
;     op 1: slots[slot] = malloc(size), then fills the block with a pattern
;     op 2: checks the pattern of slots[slot] is intact, then free(slots[slot])
;   Returns the number of problems found; ring_error holds the first one:
;     1 = malloc returned NULL, 2 = not 16-byte aligned, 3 = a block was overwritten
bits 64
global ring_workload
global ops
global nops
global ring_error
extern malloc
extern free

section .text
ring_workload:
    push rbx
    push r12
    push r13
    push r14
    push r15                        ; aligned
    xor r15d, r15d                  ; problems
    xor r12d, r12d                  ; op index
.next:
    cmp r12, [nops]
    jae .done
    lea rax, [r12 + r12*2]
    lea rbx, [ops + rax*8]          ; rbx = &ops[i]
    mov r13, [rbx + 8]              ; slot
    cmp qword [rbx], 1
    jne .free
    mov rdi, [rbx + 16]             ; size
    mov [sizes + r13*8], rdi
    call malloc
    mov [slots + r13*8], rax
    test rax, rax
    jnz .aligned_check
    mov edi, 1
    call problem
    jmp .step
.aligned_check:
    test al, 15
    jz .fill
    mov edi, 2
    call problem
.fill:
    mov rdi, [slots + r13*8]
    mov rcx, [sizes + r13*8]
    mov eax, r13d
    xor al, 0x5A
    rep stosb
    jmp .step
.free:
    mov rdi, [slots + r13*8]
    test rdi, rdi
    jz .step
    mov rcx, [sizes + r13*8]
    mov eax, r13d
    xor al, 0x5A
    repe scasb                      ; is the pattern intact?
    je .intact
    mov edi, 3
    call problem
.intact:
    mov rdi, [slots + r13*8]
    call free
    mov qword [slots + r13*8], 0
.step:
    inc r12
    jmp .next
.done:
    mov rax, r15
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

problem:                            ; edi = kind
    inc r15
    cmp qword [ring_error], 0
    jne .keep
    mov [ring_error], rdi
.keep:
    ret

section .data
ring_error: dq 0
nops:       dq 0
ops:        times 3 * 600 dq 0
slots:      times 64 dq 0
sizes:      times 64 dq 0
