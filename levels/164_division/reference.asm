    mov rax, rdi
    cqo                     ; rdx:rax = sign-extended a
    idiv rsi                ; rax = trunc(a / b), rdx = remainder (sign of a)
    mov r8, rax
    mov r9, rdx
    test rdx, rdx
    jz .done                ; exact division: floor == truncation
    cmp rdx, 0
    jl .rem_negative
    cmp rsi, 0
    jg .done                ; remainder and divisor both positive
    jmp .adjust
.rem_negative:
    cmp rsi, 0
    jl .done                ; both negative
.adjust:
    dec rax                 ; round down instead of toward zero
    add rdx, rsi            ; remainder takes the divisor's sign
.done:
