    mov rax, rdi
    shr rax, 3              ; 5 bits of red
    shl rax, 11
    mov rbx, rsi
    shr rbx, 2              ; 6 bits of green
    shl rbx, 5
    or rax, rbx
    mov rbx, rdx
    shr rbx, 3              ; 5 bits of blue
    or rax, rbx

    mov r8, r10
    mov r9, r11
    shld r9, r8, cl         ; uses cl mod 64
    shl r8, cl
    cmp ecx, 64
    jb .done
    mov r9, r8              ; n >= 64: the low word moves up entirely
    xor r8d, r8d
.done:
