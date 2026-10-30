; Level 69 — SSE Scalar (reference)

global ring_dtoa

section .rodata
thousand: dq 1000.0

section .text
ring_dtoa:                      ; xmm0 = x, rdi = buf
    mov rsi, rdi                ; the start, for the length
    ucomisd xmm0, xmm0
    jp .nan                     ; unordered with itself: a NaN
    movq rax, xmm0
    btr rax, 63                 ; CF = the sign bit; rax = |x|
    jnc .positive
    mov byte [rdi], '-'
    inc rdi
.positive:
    mov rdx, 0x7FF0000000000000
    cmp rax, rdx
    je .inf
    movq xmm0, rax
    mulsd xmm0, [rel thousand]
    cvtsd2si rax, xmm0          ; n, rounded as MXCSR says
    xor edx, edx
    mov ecx, 1000
    div rcx                     ; rax = integer part, rdx = thousandths
    mov r8, rdx
    lea r9, [rsp-32]            ; digits, backwards, in the red zone
    mov r10, r9
    mov ecx, 10
.digit:
    xor edx, edx
    div rcx
    add dl, '0'
    dec r10
    mov [r10], dl
    test rax, rax
    jnz .digit
.copy:
    mov al, [r10]
    mov [rdi], al
    inc rdi
    inc r10
    cmp r10, r9
    jne .copy
    mov byte [rdi], '.'
    mov eax, r8d
    xor edx, edx
    mov ecx, 100
    div ecx                     ; hundreds digit
    add al, '0'
    mov [rdi+1], al
    mov eax, edx
    mov cl, 10
    div cl                      ; al = tens, ah = ones
    add ax, '00'
    mov [rdi+2], ax
    add rdi, 4
    jmp .done
.nan:
    mov dword [rdi], 'nan'
    add rdi, 3
    jmp .done
.inf:
    mov dword [rdi], 'inf'
    add rdi, 3
.done:
    mov rax, rdi
    sub rax, rsi
    ret
