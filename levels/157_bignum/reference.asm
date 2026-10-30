    ; product[0 .. n+m) = 0
    lea r10, [rsi + rcx]
.clear:
    dec r10
    mov qword [product + r10*8], 0
    jnz .clear

    xor r8d, r8d                    ; i = 0
.outer:
    xor r11d, r11d                  ; carry = 0
    xor r9d, r9d                    ; j = 0
.inner:
    mov rax, [numA + r8*8]
    mul qword [numB + r9*8]         ; rdx:rax = A[i] * B[j]
    lea r10, [r8 + r9]              ; i + j
    add rax, r11                    ; + carry
    adc rdx, 0
    add rax, [product + r10*8]      ; + what is already there
    adc rdx, 0
    mov [product + r10*8], rax
    mov r11, rdx                    ; new carry
    inc r9
    cmp r9, rcx
    jb .inner
    lea r10, [r8 + rcx]
    mov [product + r10*8], r11      ; top limb of this row
    inc r8
    cmp r8, rsi
    jb .outer
