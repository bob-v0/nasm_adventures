; ---- unsigned decimal --------------------------------------------------------
    mov rax, rdi
    lea r8, [scratch + 24]          ; write digits backwards from the end
    mov r9d, 10
.u_digit:
    xor edx, edx
    div r9                          ; rax = x / 10, rdx = x % 10
    add dl, '0'
    dec r8
    mov [r8], dl
    test rax, rax
    jnz .u_digit                    ; do-while: 0 still gives "0"
    lea r10, [scratch + 24]
    sub r10, r8                     ; length
    xor ecx, ecx
.u_copy:
    mov dl, [r8 + rcx]
    mov [dec_u + rcx], dl
    inc rcx
    cmp rcx, r10
    jb .u_copy
    mov r11, r10                    ; unsigned length, for rax at the end

; ---- signed decimal ----------------------------------------------------------
    xor r12d, r12d                  ; output position
    mov rax, rdi
    test rax, rax
    jns .s_positive
    mov byte [dec_s], '-'
    inc r12
    neg rax                         ; magnitude, read as UNSIGNED (works for -2^63)
.s_positive:
    lea r8, [scratch + 24]
.s_digit:
    xor edx, edx
    div r9
    add dl, '0'
    dec r8
    mov [r8], dl
    test rax, rax
    jnz .s_digit
    lea r10, [scratch + 24]
.s_copy:
    mov dl, [r8]
    mov [dec_s + r12], dl
    inc r8
    inc r12
    cmp r8, r10
    jb .s_copy
    mov rbx, r12

; ---- hex ---------------------------------------------------------------------
    mov rax, rdi
    lea r8, [scratch + 24]
.h_digit:
    mov edx, eax
    and edx, 15
    movzx edx, byte [digits + rdx]  ; table lookup instead of if/else
    dec r8
    mov [r8], dl
    shr rax, 4
    jnz .h_digit
    mov word [hex], '0x'
    mov r12d, 2
.h_copy:
    mov dl, [r8]
    mov [hex + r12], dl
    inc r8
    inc r12
    cmp r8, r10
    jb .h_copy
    mov rcx, r12
    mov rax, r11

section .data
digits:  db "0123456789abcdef"
scratch: times 24 db 0
