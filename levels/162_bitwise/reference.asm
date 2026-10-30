    mov rax, rdi
    and rax, ~0xFFF         ; imm32 -4096, sign-extended to 0xFFFF...F000
    mov rbx, rdi
    or rbx, 0xFFF
    mov rcx, rdi
    mov r11, 1 << 63        ; a 64-bit constant needs a register
    xor rcx, r11
    mov rdx, rdi
    not rdx
    lea r8, [rdi + 0xFFF]   ; round up = add 0xFFF, then round down
    and r8, ~0xFFF
    xor r9, r9              ; zeroing idiom
    mov r10d, 0
    test rdi, 7
    jnz .unaligned
    mov r10d, 1
.unaligned:
