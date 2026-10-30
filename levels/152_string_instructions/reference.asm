    cld                         ; never trust DF

    mov rsi, src                ; 1. memcpy
    mov rdi, dst
    mov rcx, rdx
    rep movsb

    mov rdi, fill               ; 2. memset
    mov eax, r8d
    mov ecx, 32
    rep stosb

    mov rdi, str1               ; 3. strlen
    xor eax, eax
    mov rcx, -1
    repne scasb                 ; stops just after the NUL
    not rcx                     ; rcx = -(len + 2)  ->  not rcx = len + 1
    lea rax, [rcx - 1]

    xor ebx, ebx                ; 4. memcmp
    test rdx, rdx
    jz .cmp_done                ; n = 0: equal (repe with rcx = 0 sets no flags)
    mov rsi, str1
    mov rdi, str2
    mov rcx, rdx
    repe cmpsb                  ; stops after the first difference (or n bytes)
    je .cmp_done                ; flags from the last comparison: all equal
    mov rbx, 1
    mov r9, -1
    cmovb rbx, r9               ; str1 byte below str2 byte (unsigned): -1
.cmp_done:
