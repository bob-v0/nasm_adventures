; Level 120 — Pipes & dup (reference)
global _start

section .text
_start:
    mov rbx, [rsp]              ; argc
    lea r12, [rsp + 16]         ; left argv = &argv[1]
    lea rax, [rsp + rbx*8 + 16]
    mov [envp], rax
    mov r13, r12                ; find "|", replace it with NULL: right argv follows
.find:
    mov rsi, [r13]
    add r13, 8
    cmp word [rsi], '|'         ; "|", 0
    jne .find
    mov qword [r13 - 8], 0

    mov eax, 22                 ; pipe(fds)
    lea rdi, [fds]
    syscall

    mov edi, 1                  ; left: stdout -> the write end
    mov rsi, r12
    call spawn
    mov r14, rax
    xor edi, edi                ; right: stdin <- the read end
    mov rsi, r13
    call spawn
    mov r15, rax

    call close_pipe             ; the parent uses neither end
    mov rdi, r14
    call wait_for
    mov rdi, r15
    call wait_for
    mov edi, [status]           ; the pipeline's status: the right command's
    test edi, 0x7f
    jnz .signaled
    shr edi, 8
    jmp .exit
.signaled:
    and edi, 0x7f
    add edi, 128
.exit:
    mov eax, 60
    syscall

spawn:                          ; edi = 1 (left) or 0 (right), rsi = argv: returns the pid
    push rdi
    push rsi
    mov eax, 57
    syscall
    pop rsi
    pop rdi
    test rax, rax
    jz .child
    ret
.child:
    mov r12, rsi
    mov esi, edi                ; dup2(fds[edi], edi): write end for 1, read end for 0
    mov edi, [fds + rdi*4]
    mov eax, 33
    syscall
    call close_pipe
    mov eax, 59                 ; execve(argv[0], argv, envp)
    mov rdi, [r12]
    mov rsi, r12
    mov rdx, [envp]
    syscall
    mov eax, 60
    mov edi, 127
    syscall

close_pipe:
    mov eax, 3
    mov edi, [fds]
    syscall
    mov eax, 3
    mov edi, [fds + 4]
    syscall
    ret

wait_for:                       ; rdi = pid
    mov eax, 61
    lea rsi, [status]
    xor edx, edx
    xor r10d, r10d
    syscall
    ret

section .bss
envp:   resq 1
fds:    resd 2
status: resd 1
