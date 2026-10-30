global _start

section .text
_start:
    mov rbx, [rsp]                  ; argc
    lea r12, [rsp + 16]             ; &argv[1]
.args:
    mov rdi, [r12]
    test rdi, rdi
    jz .env
    call puts
    add r12, 8
    jmp .args
.env:
    add r12, 8                      ; skip argv's 0: r12 = &envp[0]
    lea rdi, [no_home]
.find_home:
    mov rsi, [r12]
    test rsi, rsi
    jz .print_home
    add r12, 8
    cmp dword [rsi], 'HOME'         ; first four bytes...
    jne .find_home
    cmp byte [rsi + 4], '='         ; ...and exactly then '='
    jne .find_home
    lea rdi, [rsi + 5]
.print_home:
    call puts
.skip_env:                          ; r12 is somewhere in envp: find its end
    cmp qword [r12], 0
    lea r12, [r12 + 8]
    jne .skip_env
.auxv:                              ; (type, value) pairs
    mov rax, [r12]
    test rax, rax
    jz .done
    cmp rax, 6                      ; AT_PAGESZ
    je .pagesz
    add r12, 16
    jmp .auxv
.pagesz:
    mov rax, [r12 + 8]
    lea rdi, [num + 20]
    mov byte [rdi], 0
    mov ecx, 10
.digit:
    xor edx, edx
    div rcx
    add dl, '0'
    dec rdi
    mov [rdi], dl
    test rax, rax
    jnz .digit
    call puts
.done:
    lea rdi, [rbx - 1]
    mov eax, 60
    syscall

puts:                               ; write the C string at rdi and a newline
    mov rsi, rdi
    xor edx, edx
.len:
    cmp byte [rsi + rdx], 0
    je .write
    inc rdx
    jmp .len
.write:
    mov eax, 1
    mov edi, 1
    syscall
    mov eax, 1
    mov edi, 1
    lea rsi, [newline]
    mov edx, 1
    syscall
    ret

section .data
no_home: db "(no HOME)", 0
newline: db 10
num:     times 21 db 0
