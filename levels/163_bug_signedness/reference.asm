; Level 163 — reference fix (4 lines)

    mov rax, rdi
    cmp rdi, rsi
    jg .have_max            ; signed comparison
    mov rax, rsi
.have_max:
    mov r8, rax

    mov rax, rdi
    cqo                     ; sign-extend a into rdx:rax
    idiv rsi                ; signed division
    mov rbx, rax

    movsx rcx, byte [delta] ; sign-extend the byte
    add rcx, rdi

    mov rax, r8
