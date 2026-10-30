    xor eax, eax                ; sum
    xor ebx, ebx                ; max
    xor ecx, ecx                ; count above threshold
    xor r8d, r8d                ; i
.top:
    cmp r8, rsi
    jae .done                   ; tested first: n = 0 runs no iterations
    mov r9, [arr + r8*8]
    add rax, r9
    cmp r9, rbx
    jbe .not_max
    mov rbx, r9
.not_max:
    cmp r9, rdx
    jbe .next
    inc rcx
.next:
    inc r8
    jmp .top
.done:
