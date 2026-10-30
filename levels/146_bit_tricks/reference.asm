    blsi rax, rdi                   ; x & -x
    blsr rbx, rdi                   ; x & (x - 1)

    lea rcx, [rdi - 1]
    lzcnt rcx, rcx                  ; 64 for x = 1
    neg ecx
    add ecx, 64                     ; bit length of x - 1
    mov edx, 1
    shl rdx, cl                     ; next power of two

    xor ecx, ecx                    ; x != 0 is given, so: power of two iff blsr gives 0
    test rbx, rbx
    sete cl

    popcnt r8, rdi
    and r8d, 1

    mov r10, rsi
    sub r10, rdi                    ; y - x
    mov r9, rdi
    sub r9, rsi                     ; x - y, CF = (x < y)
    cmovb r9, r10
