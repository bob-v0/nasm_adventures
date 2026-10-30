SA_RESTORER equ 0x04000000

global _start

section .text
_start:
    mov eax, 13                     ; rt_sigaction(SIGINT, &act_int, NULL, 8)
    mov edi, 2
    lea rsi, [act_int]
    xor edx, edx
    mov r10d, 8
    syscall
    mov eax, 13                     ; rt_sigaction(SIGSEGV, &act_segv, NULL, 8)
    mov edi, 11
    lea rsi, [act_segv]
    xor edx, edx
    mov r10d, 8
    syscall

    xor ecx, ecx
.spin:
    cmp byte [got_int], 0
    jne .caught
    inc ecx
    cmp ecx, 100000
    jb .spin
    lea rsi, [msg_none]
    mov edx, MSG_NONE_LEN
    jmp .report
.caught:
    lea rsi, [msg_int]
    mov edx, MSG_INT_LEN
.report:
    mov eax, 1
    mov edi, 1
    syscall

    mov rax, [0]                    ; SIGSEGV
recover:                            ; the handler sends us here
    mov eax, 1
    mov edi, 1
    lea rsi, [msg_segv]
    mov edx, MSG_SEGV_LEN
    syscall
    mov eax, 60
    xor edi, edi
    syscall

on_int:                             ; (signo, siginfo, ucontext)
    mov byte [got_int], 1
    ret
on_segv:
    lea rax, [recover]
    mov [rdx + 168], rax            ; ucontext->uc_mcontext.gregs[REG_RIP]
    ret
restorer:
    mov eax, 15                     ; rt_sigreturn
    syscall

section .data
act_int:  dq on_int, SA_RESTORER, restorer, 0
act_segv: dq on_segv, SA_RESTORER, restorer, 0
got_int:  db 0
msg_int:  db "caught SIGINT", 10
MSG_INT_LEN equ $ - msg_int
msg_none: db "no SIGINT", 10
MSG_NONE_LEN equ $ - msg_none
msg_segv: db "recovered from SIGSEGV", 10
MSG_SEGV_LEN equ $ - msg_segv
