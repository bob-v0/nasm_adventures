; Level 110 — Non-blocking I/O (reference)
global _start

; one input: struct source
FD     equ 0
LETTER equ 8
EOF_   equ 16
LEN    equ 24
BUF    equ 32
CAP    equ 512

section .text
_start:
    mov eax, 72                 ; fcntl(3, F_SETFL, O_NONBLOCK)
    mov edi, 3
    mov esi, 4
    mov edx, 0o4000
    syscall
    mov eax, 72                 ; fcntl(4, F_SETFL, O_NONBLOCK)
    mov edi, 4
    mov esi, 4
    mov edx, 0o4000
    syscall
.poll:
    lea rbx, [src_a]
    call service
    mov r12, rax                ; did A have anything?
    lea rbx, [src_b]
    call service
    or r12, rax
    mov rax, [src_a + EOF_]
    and rax, [src_b + EOF_]
    jnz .done
    test r12, r12
    jnz .poll                   ; something came in: look again right away
    mov eax, 35                 ; nothing: sleep 1 ms instead of spinning
    lea rdi, [one_ms]
    xor esi, esi
    syscall
    jmp .poll
.done:
    mov eax, 1
    mov edi, 1
    lea rsi, [done_msg]
    mov edx, 5
    syscall
    mov eax, 60
    xor edi, edi
    syscall

service:                        ; rbx = source: read what's there, print complete lines
    xor eax, eax                ; returns rax = 1 if it read anything
    cmp qword [rbx + EOF_], 0
    jne .ret
    xor eax, eax                ; read(fd, buf + len, CAP - len)
    mov rdi, [rbx + FD]
    mov rdx, [rbx + LEN]
    lea rsi, [rbx + BUF + rdx]
    neg rdx
    add rdx, CAP
    syscall
    cmp rax, -11                ; EAGAIN: nothing yet
    je .nothing
    test rax, rax
    jg .got
    mov qword [rbx + EOF_], 1   ; 0 (or an error): this source is finished
    jmp .ret1
.got:
    add [rbx + LEN], rax
.line:                          ; print every complete line at the front of the buffer
    xor ecx, ecx
.find:
    cmp rcx, [rbx + LEN]
    jae .ret1
    cmp byte [rbx + BUF + rcx], 10
    je .print
    inc rcx
    jmp .find
.print:
    lea r13, [rcx + 1]          ; line length with the newline
    mov rax, [rbx + LETTER]     ; "A: "
    mov [prefix], al
    mov eax, 1
    mov edi, 1
    lea rsi, [prefix]
    mov edx, 3
    syscall
    mov eax, 1
    mov edi, 1
    lea rsi, [rbx + BUF]
    mov rdx, r13
    syscall
    xor ecx, ecx                ; move the rest to the front
.shift:
    lea rdx, [rcx + r13]
    cmp rdx, [rbx + LEN]
    jae .shifted
    mov al, [rbx + BUF + rdx]
    mov [rbx + BUF + rcx], al
    inc rcx
    jmp .shift
.shifted:
    sub [rbx + LEN], r13
    jmp .line
.ret1:
    mov eax, 1
    ret
.nothing:
    xor eax, eax
.ret:
    ret

section .data
src_a:  dq 3, 'A', 0, 0
        times CAP db 0
src_b:  dq 4, 'B', 0, 0
        times CAP db 0
prefix: db "?: "
done_msg: db "done", 10
one_ms: dq 0, 1_000_000
