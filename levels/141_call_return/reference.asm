global print_uint

section .text
; utoa(rdi = n, rsi = end of buffer) -> rax = start of the digits, rdx = length.
; Writes the digits right-aligned, ending just before rsi.
utoa:
    mov rax, rdi
    mov rcx, rsi
    mov r8d, 10
.digit:
    xor edx, edx
    div r8
    add dl, '0'
    dec rcx
    mov [rcx], dl
    test rax, rax
    jnz .digit
    mov rax, rcx
    mov rdx, rsi
    sub rdx, rcx
    ret

; print_uint(rdi = n) -> rax = bytes written
print_uint:
    sub rsp, 32                     ; local buffer: rsp .. rsp+31
    mov byte [rsp + 31], 10         ; newline at the end
    lea rsi, [rsp + 31]             ; digits go just before it
    call utoa
    lea rdx, [rdx + 1]              ; digits + newline
    mov rsi, rax
    mov eax, 1                      ; write(1, digits, len)
    mov edi, 1
    syscall
    add rsp, 32
    ret
