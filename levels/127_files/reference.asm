global _start

section .text
_start:
    mov eax, 2                  ; open("in.txt", O_RDONLY)
    lea rdi, [in_name]
    xor esi, esi
    syscall
    test rax, rax
    js .open_failed
    mov r12, rax                ; in fd
    mov eax, 2                  ; open("out.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644)
    lea rdi, [out_name]
    mov esi, 1 | 0o100 | 0o1000
    mov edx, 0o644
    syscall
    mov r13, rax                ; out fd
    xor r14d, r14d              ; newline count
.copy:
    xor eax, eax                ; read(in, buf, 4096)
    mov rdi, r12
    lea rsi, [buf]
    mov edx, 4096
    syscall
    test rax, rax
    jle .copied                 ; 0 = end of file
    mov r15, rax
    xor ecx, ecx
.count:
    cmp byte [buf + rcx], 10
    jne .not_nl
    inc r14
.not_nl:
    inc rcx
    cmp rcx, r15
    jb .count
    mov eax, 1                  ; write(out, buf, n)
    mov rdi, r13
    lea rsi, [buf]
    mov rdx, r15
    syscall
    jmp .copy
.copied:
    mov eax, 3                  ; close both
    mov rdi, r12
    syscall
    mov eax, 3
    mov rdi, r13
    syscall
    lea rsi, [num + 20]         ; format "N lines\n"
    mov rax, r14
    mov ecx, 10
.digit:
    xor edx, edx
    div rcx
    add dl, '0'
    dec rsi
    mov [rsi], dl
    test rax, rax
    jnz .digit
    lea rdx, [num + 20 + LINES_LEN]
    sub rdx, rsi
    mov eax, 1
    mov edi, 1
    syscall
    mov eax, 60
    xor edi, edi
    syscall
.open_failed:
    neg rax
    mov rbx, rax                ; errno
    mov eax, 1
    mov edi, 2
    lea rsi, [cannot]
    mov edx, CANNOT_LEN
    syscall
    mov eax, 60
    mov rdi, rbx
    syscall

section .data
in_name:  db "in.txt", 0
out_name: db "out.txt", 0
cannot:   db "cannot open in.txt", 10
CANNOT_LEN equ $ - cannot
num:      times 20 db 0
          db " lines", 10
LINES_LEN equ 7

section .bss
buf: resb 4096
