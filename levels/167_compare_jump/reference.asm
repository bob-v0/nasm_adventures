    mov rax, rdi
    cmp rax, rsi
    jge .s_lo_ok            ; signed: x >= lo?
    mov rax, rsi
.s_lo_ok:
    cmp rax, rdx
    jle .s_done             ; signed: x <= hi?
    mov rax, rdx
.s_done:

    mov rbx, rdi
    cmp rbx, rsi
    jae .u_lo_ok            ; unsigned: above or equal
    mov rbx, rsi
.u_lo_ok:
    cmp rbx, rdx
    jbe .u_done             ; unsigned: below or equal
    mov rbx, rdx
.u_done:
