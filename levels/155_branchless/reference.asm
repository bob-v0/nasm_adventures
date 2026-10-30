    mov rax, rdi
    neg rax                 ; -a; flags describe -a
    cmovl rax, rdi          ; if -a < 0 (a > 0), use a. For -2^63: OF=1, so not "less"

    mov rbx, rdi
    cmp rsi, rdi
    cmovl rbx, rsi          ; b < a (signed): min is b

    mov rcx, rdi
    cmp rsi, rdi
    cmova rcx, rsi          ; b > a (unsigned): max is b

    xor edx, edx            ; zero before the cmp: xor changes flags
    xor r10d, r10d
    test rdi, rdi
    setg dl
    setl r10b
    sub rdx, r10            ; (a > 0) - (a < 0)

    xor r8d, r8d
    cmp rdi, rsi
    sete r8b
