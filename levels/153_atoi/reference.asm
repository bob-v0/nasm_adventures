    mov rsi, text
    xor r8d, r8d                    ; 1 = negative
    xor r11d, r11d                  ; 1 = overflowed (keep scanning for bad characters)
    movzx eax, byte [rsi]
    cmp al, '-'
    jne .not_minus
    mov r8d, 1
    inc rsi
    jmp .prefix
.not_minus:
    cmp al, '+'
    jne .prefix
    inc rsi
.prefix:
    mov r9d, 10                     ; base
    cmp byte [rsi], '0'
    jne .digits
    movzx edx, byte [rsi + 1]
    or dl, 0x20                     ; 'X' -> 'x'
    cmp dl, 'x'
    jne .digits
    mov r9d, 16
    add rsi, 2
.digits:
    xor eax, eax                    ; magnitude (unsigned)
    xor ecx, ecx                    ; digits seen
.next:
    movzx r10d, byte [rsi]
    test r10d, r10d
    jz .end
    cmp r10b, '0'
    jb .invalid
    cmp r10b, '9'
    jbe .decimal
    cmp r9d, 16
    jne .invalid
    or r10b, 0x20                   ; lowercase
    cmp r10b, 'a'
    jb .invalid
    cmp r10b, 'f'
    ja .invalid
    sub r10d, 'a' - 10
    jmp .accumulate
.decimal:
    sub r10d, '0'
.accumulate:
    inc ecx
    inc rsi
    test r11d, r11d
    jnz .next                       ; already too big: just validate the rest
    mul r9                          ; rdx:rax = value * base
    jc .too_big
    add rax, r10
    jc .too_big
    jmp .next
.too_big:
    mov r11d, 1
    jmp .next
.end:
    test ecx, ecx
    jz .invalid                     ; no digits at all
    test r11d, r11d
    jnz .overflow
    mov rdx, 1 << 63                ; limit: 2^63 - 1, or 2^63 when negative
    sub rdx, 1
    add rdx, r8
    cmp rax, rdx
    ja .overflow
    test r8d, r8d
    jz .ok
    neg rax
.ok:
    xor ebx, ebx
    jmp .done
.invalid:
    xor eax, eax
    mov ebx, 1
    jmp .done
.overflow:
    xor eax, eax
    mov ebx, 2
.done:
