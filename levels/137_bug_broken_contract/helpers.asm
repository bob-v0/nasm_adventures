; Provided by level 137.
;   ring_mix(b): mixes one byte into a checksum term; counts misaligned calls and,
;                like any function, clobbers the caller-saved registers.
;   ring_app(buf, len): the "application" the game runs. It keeps important values
;                in callee-saved registers, calls frame(buf, len), and checks they
;                survived. It returns frame's result in rax.
bits 64
global ring_mix
global ring_app
global ring_misaligned
global ring_corrupted
global packet
extern frame

section .text
ring_mix:                       ; rdi = byte -> rax = byte * 31 + 7
    lea rax, [rsp + 8]
    test al, 15
    jz .aligned
    inc qword [ring_misaligned]
.aligned:
    imul rax, rdi, 31
    add rax, 7
    mov rcx, 0x5C5C5C5C5C5C5C5C
    mov rdx, rcx
    mov rsi, rcx
    mov rdi, rcx
    mov r8, rcx
    mov r9, rcx
    mov r10, rcx
    mov r11, rcx
    ret

ring_app:                       ; rdi = buf, rsi = len
    push rbx
    push r12
    push r13
    mov rbx, 0x1111111111111111 ; the application's own state...
    mov r12, 0x2222222222222222
    mov r13, 0x3333333333333333
    call frame                  ; (rsp is aligned here: 3 pushes after the call)
    mov rcx, 0x1111111111111111 ; ...must survive the call
    cmp rbx, rcx
    jne .corrupt
    mov rcx, 0x2222222222222222
    cmp r12, rcx
    jne .corrupt
    mov rcx, 0x3333333333333333
    cmp r13, rcx
    je .ok
.corrupt:
    inc qword [ring_corrupted]
.ok:
    pop r13
    pop r12
    pop rbx
    ret

section .data
ring_misaligned: dq 0
ring_corrupted:  dq 0
packet:          times 64 db 0
