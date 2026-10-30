    xor eax, eax                ; lo
    mov rcx, rsi                ; hi       invariant: answer in [lo, hi)
.loop:
    cmp rax, rcx
    jae .done
    mov rdx, rcx
    sub rdx, rax
    shr rdx, 1
    add rdx, rax                ; mid = lo + (hi - lo) / 2
    cmp [arr + rdx*8], rdi
    jae .left                   ; arr[mid] >= key: answer is mid or below
    lea rax, [rdx + 1]
    jmp .loop
.left:
    mov rcx, rdx
    jmp .loop
.done:
