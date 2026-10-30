    mov r8d, 1                      ; i
.outer:
    cmp r8, rsi
    jae .done                       ; also covers n = 0 and n = 1
    mov rax, [arr + r8*8]           ; x
    mov r9, r8                      ; j
.inner:
    test r9, r9
    jz .place
    mov rdx, [arr + r9*8 - 8]
    cmp rdx, rax
    jle .place                      ; signed; stop at <= keeps the sort stable
    mov [arr + r9*8], rdx
    dec r9
    jmp .inner
.place:
    mov [arr + r9*8], rax
    inc r8
    jmp .outer
.done:
