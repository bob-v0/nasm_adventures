; Level 112 — Directories & mmap (reference)
global _start

section .text
_start:
    mov rsi, [rsp + 16]         ; copy argv[1] into path
    xor ecx, ecx
.copy:
    mov al, [rsi + rcx]
    mov [path + rcx], al
    inc ecx
    test al, al
    jnz .copy
    lea r15, [rcx - 1]          ; r15 = length of path (global)
    call walk
    lea rsi, [total_msg]
    call print
    mov rax, [total]
    call print_number
    mov eax, 60
    xor edi, edi
    syscall

walk:                           ; path is a directory: visit everything in it
    push rbx
    push r12
    push r13
    push r14
    push rbp
    sub rsp, 1024               ; this level's getdents64 buffer
    mov eax, 2                  ; open(path, O_RDONLY | O_DIRECTORY)
    lea rdi, [path]
    mov esi, 0o200000
    syscall
    test rax, rax
    js .out
    mov rbx, rax
.batch:
    mov eax, 217                ; getdents64(fd, buf, 1024)
    mov rdi, rbx
    mov rsi, rsp
    mov edx, 1024
    syscall
    test rax, rax
    jle .end
    mov r12, rax
    xor r13d, r13d
.entry:
    cmp r13, r12
    jae .batch
    lea r14, [rsp + r13]        ; struct linux_dirent64
    cmp byte [r14 + 19], '.'    ; skip "." and ".." (and hidden files)
    je .skip
    mov rbp, r15                ; path += "/" + name
    mov byte [path + r15], '/'
    inc r15
    lea rsi, [r14 + 19]
.append:
    mov al, [rsi]
    mov [path + r15], al
    inc rsi
    inc r15
    test al, al
    jnz .append
    dec r15
    movzx eax, byte [r14 + 18]  ; d_type
    cmp eax, 4                  ; DT_DIR
    jne .file
    call walk
    jmp .restore
.file:
    cmp eax, 8                  ; DT_REG (symlinks and others are skipped)
    jne .restore
    call count_file
.restore:
    mov r15, rbp
    mov byte [path + r15], 0
.skip:
    movzx eax, word [r14 + 16]  ; d_reclen
    add r13, rax
    jmp .entry
.end:
    mov eax, 3
    mov rdi, rbx
    syscall
.out:
    add rsp, 1024
    pop rbp
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

count_file:                     ; path is a regular file: print "path: words"
    push rbx
    push r12
    push r13
    mov eax, 2
    lea rdi, [path]
    xor esi, esi
    syscall
    mov rbx, rax
    mov eax, 5                  ; fstat(fd, &st): st_size at offset 48
    mov rdi, rbx
    lea rsi, [st]
    syscall
    mov r12, [st + 48]
    xor r13d, r13d              ; words
    test r12, r12
    jz .report                  ; mmap(length 0) fails: an empty file has no words
    mov eax, 9                  ; mmap(0, size, PROT_READ, MAP_PRIVATE, fd, 0)
    xor edi, edi
    mov rsi, r12
    mov edx, 1
    mov r10d, 2
    mov r8, rbx
    xor r9d, r9d
    syscall
    mov rdi, rax
    xor ecx, ecx                ; index
    xor edx, edx                ; inside a word?
.byte:
    movzx eax, byte [rdi + rcx]
    cmp al, ' '
    je .space
    cmp al, 10
    je .space
    cmp al, 9
    je .space
    test edx, edx
    jnz .next
    inc r13
    mov edx, 1
    jmp .next
.space:
    xor edx, edx
.next:
    inc rcx
    cmp rcx, r12
    jb .byte
    mov eax, 11                 ; munmap(addr, size)
    mov rsi, r12
    syscall
.report:
    mov eax, 3
    mov rdi, rbx
    syscall
    add [total], r13
    lea rsi, [path]
    call print
    lea rsi, [colon]
    call print
    mov rax, r13
    call print_number
    pop r13
    pop r12
    pop rbx
    ret

print:                          ; rsi = C string
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
    ret

print_number:                   ; rax = n, then a newline
    lea rsi, [digits + 22]
    mov byte [rsi], 0
    dec rsi
    mov byte [rsi], 10
    mov ecx, 10
.digit:
    xor edx, edx
    div rcx
    add dl, '0'
    dec rsi
    mov [rsi], dl
    test rax, rax
    jnz .digit
    jmp print

section .data
colon:     db ": ", 0
total_msg: db "total: ", 0

section .bss
total:  resq 1
st:     resb 144
digits: resb 24
path:   resb 4096
