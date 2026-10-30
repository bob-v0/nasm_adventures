global _start

section .text
_start:
    xor eax, eax                    ; read(0, line, 255)
    xor edi, edi
    mov rsi, line
    mov edx, 255
    syscall
    test rax, rax
    js error
    mov byte [line + rax], 0
    mov [saved_rsp], rsp            ; for escaping from deep recursion on errors
    mov rbx, line                   ; the cursor, shared by all the parsing functions
    call expr
    mov r12, rax
    call skip_spaces
    movzx eax, byte [rbx]
    test al, al
    jz .print
    cmp al, 10
    jne error
.print:
    mov rdi, r12
    call print_int
    mov eax, 60
    xor edi, edi
    syscall

error:
    mov rsp, [saved_rsp]            ; unwind every frame at once (like longjmp)
    mov eax, 1
    mov edi, 1
    mov rsi, error_msg
    mov edx, 6
    syscall
    mov eax, 60
    mov edi, 1
    syscall

skip_spaces:
    cmp byte [rbx], ' '
    jne .done
    inc rbx
    jmp skip_spaces
.done:
    ret

expr:                               ; -> rax
    push r12                        ; aligned for our calls
    call term
    mov r12, rax
.loop:
    call skip_spaces
    movzx eax, byte [rbx]
    cmp al, '+'
    je .add
    cmp al, '-'
    je .sub
    mov rax, r12
    pop r12
    ret
.add:
    inc rbx
    call term
    add r12, rax
    jmp .loop
.sub:
    inc rbx
    call term
    sub r12, rax
    jmp .loop

term:                               ; -> rax
    push r12
    call factor
    mov r12, rax
.loop:
    call skip_spaces
    movzx eax, byte [rbx]
    cmp al, '*'
    je .mul
    cmp al, '/'
    je .div
    mov rax, r12
    pop r12
    ret
.mul:
    inc rbx
    call factor
    imul r12, rax
    jmp .loop
.div:
    inc rbx
    call factor
    test rax, rax
    jz error                        ; division by zero
    cmp rax, -1
    jne .divide
    mov rcx, 1 << 63
    cmp r12, rcx
    je error                        ; -2^63 / -1 doesn't fit
.divide:
    mov rcx, rax
    mov rax, r12
    cqo
    idiv rcx
    mov r12, rax
    jmp .loop

factor:                             ; -> rax
    sub rsp, 8                      ; aligned for our calls
    call skip_spaces
    movzx eax, byte [rbx]
    cmp al, '-'
    je .negate
    cmp al, '('
    je .paren
    sub al, '0'
    cmp al, 9
    ja error                        ; not a digit (unsigned compare catches both sides)
    xor eax, eax
.digit:
    movzx ecx, byte [rbx]
    sub ecx, '0'
    cmp ecx, 9
    ja .number_done
    imul rax, rax, 10
    jo error                        ; too big
    add rax, rcx
    jo error
    inc rbx
    jmp .digit
.number_done:
    add rsp, 8
    ret
.negate:
    inc rbx
    call factor
    neg rax
    add rsp, 8
    ret
.paren:
    inc rbx
    call expr                       ; expr returns with the cursor on a non-space
    cmp byte [rbx], ')'
    jne error
    inc rbx
    add rsp, 8
    ret

print_int:                          ; rdi = signed value; prints it and a newline
    lea rsi, [numbuf + 31]
    mov byte [rsi], 10
    mov rax, rdi
    test rax, rax
    jns .digits
    neg rax                         ; magnitude, read as unsigned (works for -2^63)
.digits:
    mov ecx, 10
.next:
    xor edx, edx
    div rcx
    add dl, '0'
    dec rsi
    mov [rsi], dl
    test rax, rax
    jnz .next
    test rdi, rdi
    jns .write
    dec rsi
    mov byte [rsi], '-'
.write:
    lea rdx, [numbuf + 32]
    sub rdx, rsi
    mov eax, 1
    mov edi, 1
    syscall
    ret

section .data
error_msg: db "error", 10

section .bss
line:      resb 256
numbuf:    resb 32
saved_rsp: resq 1
