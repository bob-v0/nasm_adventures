    cld
    mov rdi, tape                   ; clear the tape
    mov ecx, 4096
    xor eax, eax
    rep stosb

    xor esi, esi                    ; ip
    xor edi, edi                    ; dp
    xor r8d, r8d                    ; input position
    xor eax, eax                    ; output length
.fetch:
    movzx ecx, byte [program + rsi]
    test ecx, ecx
    jz .done
    cmp cl, '>'
    je .right
    cmp cl, '<'
    je .left
    cmp cl, '+'
    je .inc
    cmp cl, '-'
    je .dec
    cmp cl, '.'
    je .out
    cmp cl, ','
    je .in
    cmp cl, '['
    je .open
    cmp cl, ']'
    je .close
.step:
    inc rsi
    jmp .fetch

.right:
    inc rdi
    jmp .step
.left:
    dec rdi
    jmp .step
.inc:
    inc byte [tape + rdi]
    jmp .step
.dec:
    dec byte [tape + rdi]
    jmp .step
.out:
    movzx ecx, byte [tape + rdi]
    mov [output + rax], cl
    inc rax
    jmp .step
.in:
    xor ecx, ecx                    ; 0 at end of input
    cmp r8, rdx
    jae .store
    movzx ecx, byte [input + r8]
    inc r8
.store:
    mov [tape + rdi], cl
    jmp .step
.open:
    cmp byte [tape + rdi], 0
    jne .step
    mov r9d, 1                      ; depth: find the matching ]
.fwd:
    inc rsi
    movzx ecx, byte [program + rsi]
    cmp cl, '['
    jne .fwd_close
    inc r9
.fwd_close:
    cmp cl, ']'
    jne .fwd
    dec r9
    jnz .fwd
    jmp .step                       ; continue after the ]
.close:
    cmp byte [tape + rdi], 0
    je .step
    mov r9d, 1                      ; find the matching [
.back:
    dec rsi
    movzx ecx, byte [program + rsi]
    cmp cl, ']'
    jne .back_open
    inc r9
.back_open:
    cmp cl, '['
    jne .back
    dec r9
    jnz .back
    jmp .step                       ; continue after the [
.done:
