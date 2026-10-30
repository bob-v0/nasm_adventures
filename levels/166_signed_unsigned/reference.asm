    mov eax, 0              ; flags are untouched by mov...
    mov r10, rdi
    add r10, rsi            ; ...so CF here is the carry of a + b
    adc rax, 0              ; rax = CF

    mov ebx, 0
    mov r10, rdi
    add r10, rsi
    jno .add_ok
    mov ebx, 1
.add_ok:
    mov ecx, 0
    mov r10, rdi
    sub r10, rsi
    adc rcx, 0              ; CF after sub = borrow

    mov edx, 0
    mov r10, rdi
    sub r10, rsi
    jno .sub_ok
    mov edx, 1
.sub_ok:
    mov r8d, 0
    cmp rdi, rsi
    jge .not_less
    mov r8d, 1
.not_less:
    mov r9d, 0
    cmp rdi, rsi
    jae .not_below
    mov r9d, 1
.not_below:
