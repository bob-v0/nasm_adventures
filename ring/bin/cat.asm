; cat [FILE...]: copies the files (or stdin) to stdout. Exit 1 if a file can't be opened.
%include "_common.inc"
global _start
section .text
_start:
    lea r12, [rsp + 16]         ; argv[1]
    xor r14d, r14d              ; exit status
    cmp qword [r12], 0
    jne .files
    xor edi, edi
    call copy
    jmp .done
.files:
    mov rdi, [r12]
    test rdi, rdi
    jz .done
    mov eax, 2                  ; open(path, O_RDONLY)
    xor esi, esi
    syscall
    test rax, rax
    js .fail
    mov r13, rax
    mov rdi, rax
    call copy
    mov eax, 3
    mov rdi, r13
    syscall
    add r12, 8
    jmp .files
.fail:
    WRITE 2, msg, MSG_LEN
    mov r14d, 1
    add r12, 8
    jmp .files
.done:
    EXIT r14d

copy:                           ; rdi = fd: copy it to stdout (handles short writes)
    push rbx
    mov rbx, rdi
.read:
    xor eax, eax
    mov rdi, rbx
    lea rsi, [buf]
    mov edx, 4096
    syscall
    test rax, rax
    jle .eof
    lea rsi, [buf]
    mov rdx, rax
.write:
    mov eax, 1
    mov edi, 1
    syscall
    test rax, rax
    jle .eof                    ; e.g. EPIPE: stop
    add rsi, rax
    sub rdx, rax
    jnz .write
    jmp .read
.eof:
    pop rbx
    ret
section .data
msg: db "cat: cannot open file", 10
MSG_LEN equ $ - msg
section .bss
buf: resb 4096
