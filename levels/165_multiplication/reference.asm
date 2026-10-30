imul r9, rdi, 37        ; three-operand form
mov r10, rdi
imul r10, rsi           ; low 64 bits; OF = CF = signed overflow
mov r8d, 0
adc r8, 0               ; r8 = CF (mov did not touch it)
mov rax, rdi
mul rsi                 ; rdx:rax = full unsigned product (overwrites rdx)
