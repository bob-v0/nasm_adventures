; Level 132 — reference fix
;
; format_pair(rdi = a, rsi = b, rdx = out) formats "a,b" (unsigned decimals) as a
; C string and returns a pointer to it. `out` is a 48-byte buffer owned by the caller.
;
; When the caller prints the result straight away, it looks right. When it formats
; two pairs and then prints both, it gets garbage. Fix it, changing at most 2 lines.

global format_pair

section .text
format_pair:
    push rbx
    push r12
    sub rsp, 40                 ; a 40-byte buffer for the text
    mov rbx, rsi                ; keep b
    mov r12, rdx                ; keep out
    mov rsi, r12                ; fix: write into the caller's buffer
    call put_uint               ; a
    mov byte [rax], ','
    lea rsi, [rax + 1]
    mov rdi, rbx
    call put_uint               ; b
    mov byte [rax], 0
    mov rax, r12                ; fix: which outlives this call
    add rsp, 40
    pop r12
    pop rbx
    ret

; put_uint(rdi = n, rsi = dst) -> rax = just past the digits written at dst
put_uint:
    mov rax, rdi
    mov rcx, rsi
    mov r8d, 10
.count:                         ; first find where the last digit goes
    inc rcx
    xor edx, edx
    div r8
    test rax, rax
    jnz .count
    mov r9, rcx                 ; end
    mov rax, rdi
.digit:                         ; then write the digits backwards
    xor edx, edx
    div r8
    add dl, '0'
    dec rcx
    mov [rcx], dl
    test rax, rax
    jnz .digit
    mov rax, r9
    ret
