; ---- reverse --------------------------------------------------------------------
    xor ecx, ecx                    ; number of characters pushed
.push_chars:
    movzx eax, byte [text + rcx]
    test eax, eax
    jz .pop_chars
    push rax
    inc rcx
    jmp .push_chars
.pop_chars:
    xor edx, edx                    ; output position
.pop_next:
    cmp rdx, rcx
    jae .reversed
    pop rax                         ; last pushed comes out first
    mov [out + rdx], al
    inc rdx
    jmp .pop_next
.reversed:
    mov byte [out + rdx], 0

; ---- brackets ---------------------------------------------------------------------
    xor ecx, ecx                    ; open brackets on the stack
    xor esi, esi                    ; position in text
    mov eax, 1                      ; assume balanced
.scan:
    movzx edx, byte [text + rsi]
    inc rsi
    test edx, edx
    jz .end
    cmp dl, '('
    je .open
    cmp dl, '['
    je .open
    cmp dl, '{'
    je .open
    mov r8d, '('
    cmp dl, ')'
    je .close
    mov r8d, '['
    cmp dl, ']'
    je .close
    mov r8d, '{'
    cmp dl, '}'
    jne .scan
.close:
    test rcx, rcx
    jz .bad                         ; nothing to close
    pop r9
    dec rcx
    cmp r9, r8
    jne .bad
    jmp .scan
.open:
    push rdx
    inc rcx
    jmp .scan
.end:
    test rcx, rcx
    jz .clean
.bad:
    xor eax, eax
.clean:
    lea rsp, [rsp + rcx*8]          ; drop whatever is still pushed
