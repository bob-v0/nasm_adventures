    mov rax, 0xCBF29CE484222325     ; FNV offset basis
    mov r8, 0x100000001B3           ; FNV prime
    mov ebx, 0xFFFFFFFF             ; CRC initial value
    mov rsi, text
.next:
    movzx edx, byte [rsi]
    test dl, dl
    jz .done
    xor rax, rdx
    imul rax, r8
    crc32 ebx, dl
    inc rsi
    jmp .next
.done:
    not ebx                         ; 32-bit write: upper half of rbx is 0
