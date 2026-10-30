movzx ebx, al        ; 32-bit destination: upper half of rbx cleared too
movsx rcx, ax
movsxd rdx, eax
movzx esi, ah        ; `movzx rsi, ah` cannot be encoded (REX + ah)
mov edi, eax         ; a 32-bit write zero-extends by itself
mov r8, rax
mov r8b, 0x7F        ; an 8-bit write leaves the other 56 bits alone
