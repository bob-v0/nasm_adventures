global dot
global cmp_desc
global count_char

section .text
dot:                            ; rdi = a, rsi = b, rdx = n
    xor eax, eax
    xor ecx, ecx
.next:
    cmp rcx, rdx
    jae .done
    mov r8, [rdi + rcx*8]
    imul r8, [rsi + rcx*8]
    add rax, r8
    inc rcx
    jmp .next
.done:
    ret

cmp_desc:                       ; rdi, rsi = pointers to int64_t
    mov rcx, [rdi]
    mov rdx, [rsi]
    xor eax, eax
    cmp rcx, rdx
    je .equal
    mov eax, 1                  ; *x < *y: x goes after y
    mov r8d, -1
    cmovg eax, r8d              ; *x > *y: x goes first
.equal:
    ret

count_char:                     ; rdi = s, esi = c
    xor eax, eax
.scan:
    movzx ecx, byte [rdi]
    test ecx, ecx
    jz .end
    cmp cl, sil
    jne .skip
    inc rax
.skip:
    inc rdi
    jmp .scan
.end:
    ret
