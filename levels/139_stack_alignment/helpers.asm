; Provided by level 139. ring_square(x) returns x * x. It insists, as the ABI
; requires (and as real library code like printf does), that rsp was 16-byte
; aligned at the call, i.e. rsp % 16 == 8 on entry. Each violation is counted.
bits 64
global ring_square
global ring_calls
global ring_misaligned

section .text
ring_square:
    inc qword [ring_calls]
    lea rax, [rsp + 8]
    test al, 15
    jz .aligned
    inc qword [ring_misaligned]
.aligned:
    mov rax, rdi
    imul rax, rdi
    mov rcx, 0x5C5C5C5C5C5C5C5C
    mov rdx, rcx
    mov rsi, rcx
    mov rdi, rcx
    mov r8, rcx
    mov r9, rcx
    mov r10, rcx
    mov r11, rcx
    ret

section .data
ring_calls:      dq 0
ring_misaligned: dq 0
