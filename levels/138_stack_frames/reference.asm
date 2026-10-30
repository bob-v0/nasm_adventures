global backtrace

section .text
backtrace:
    xor eax, eax
    test rsi, rsi
    jz .done
    mov rcx, [rsp]                  ; our own return address
    mov [rdi], rcx
    mov eax, 1
    mov rdx, rbp                    ; walk a copy: rbp itself is callee-saved
.walk:
    cmp rax, rsi
    jae .done
    test rdx, rdx
    jz .done
    mov rcx, [rdx + 8]              ; this frame's return address
    mov [rdi + rax*8], rcx
    inc rax
    mov rdx, [rdx]                  ; the caller's frame
    jmp .walk
.done:
    ret
