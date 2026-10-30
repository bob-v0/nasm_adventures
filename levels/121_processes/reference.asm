; Level 121 — Processes (reference)
global _start

section .text
_start:
    mov rbx, [rsp]              ; argc
    lea r12, [rsp + 16]         ; argv[1]
    lea rax, [rsp + rbx*8 + 16] ; envp
    mov [envp], rax
    xor r15d, r15d              ; commands that didn't exit 0
.next:
    mov r13, [r12]
    test r13, r13
    jz .done
    mov eax, 57                 ; fork()
    syscall
    test rax, rax
    jz .child
    mov r14, rax
    mov eax, 61                 ; wait4(pid, &status, 0, 0)
    mov rdi, r14
    lea rsi, [status]
    xor edx, edx
    xor r10d, r10d
    syscall
    mov rsi, r13                ; "cmd: "
    call print
    lea rsi, [colon]
    call print
    mov eax, [status]
    test eax, 0x7f
    jnz .killed
    lea rsi, [exited]
    call print
    movzx eax, byte [status + 1]
    jmp .report
.killed:
    lea rsi, [killed]
    call print
    mov eax, [status]
    and eax, 0x7f
.report:
    test eax, eax
    setnz cl
    movzx ecx, cl
    add r15d, ecx
    call print_number
    add r12, 8
    jmp .next
.done:
    mov eax, 60
    mov edi, r15d
    syscall

.child:
    mov [args], r13             ; argv = [path, 0]
    mov eax, 59                 ; execve(path, args, envp)
    mov rdi, r13
    lea rsi, [args]
    mov rdx, [envp]
    syscall
    mov rsi, r13                ; only reached if execve failed
    mov edi, 2
    call print_to
    lea rsi, [cannot]
    mov edi, 2
    call print_to
    mov eax, 60
    mov edi, 127
    syscall

print:                          ; rsi = C string, to stdout
    mov edi, 1
print_to:                       ; rdi = fd, rsi = C string
    xor edx, edx
.len:
    cmp byte [rsi + rdx], 0
    je .write
    inc rdx
    jmp .len
.write:
    mov eax, 1
    syscall
    ret

print_number:                   ; eax = n: prints it and a newline
    lea rsi, [digits + 15]
    mov byte [rsi], 0
    mov ecx, 10
.digit:
    xor edx, edx
    div ecx
    add dl, '0'
    dec rsi
    mov [rsi], dl
    test eax, eax
    jnz .digit
    call print
    lea rsi, [newline]
    jmp print

section .data
colon:   db ": ", 0
exited:  db "exited ", 0
killed:  db "killed by signal ", 0
cannot:  db ": cannot execute", 10, 0
newline: db 10, 0

section .bss
envp:   resq 1
args:   resq 2
status: resd 1
digits: resb 16
