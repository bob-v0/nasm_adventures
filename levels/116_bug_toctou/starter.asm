; Level 116 — Time of Check, Time of Use
;
; showfile PATH: a privileged helper (it runs with root's rights, so open() succeeds on
; any file). It must only print files that the user who ran it (uid 1000) may read:
; files the user owns, or files readable by everyone. Otherwise it writes
; "access denied\n" to stderr and exits 1.
;
; It checks with access(), which answers for the real user. A user who can change
; PATH between the check and the open can make it print /etc/shadow.
;
; Write a witness:  ;! witness after = "SYSCALL"   (the attacker strikes right after
; your program's first call of SYSCALL), then fix the program.

global _start

section .text
_start:
    mov rbx, [rsp + 16]         ; PATH = argv[1]
    mov eax, 21                 ; access(PATH, R_OK): may the real user read it?
    mov rdi, rbx
    mov esi, 4
    syscall
    test rax, rax
    js denied
    mov eax, 2                  ; open(PATH, O_RDONLY)
    mov rdi, rbx
    xor esi, esi
    syscall
    test rax, rax
    js denied
    mov r12, rax
copy:
    xor eax, eax                ; read(fd, buf, 4096)
    mov rdi, r12
    lea rsi, [buf]
    mov edx, 4096
    syscall
    test rax, rax
    jle done
    mov rdx, rax                ; write(1, buf, n)
    mov eax, 1
    mov edi, 1
    lea rsi, [buf]
    syscall
    jmp copy
done:
    mov eax, 3
    mov rdi, r12
    syscall
    mov eax, 60
    xor edi, edi
    syscall
denied:
    mov eax, 1
    mov edi, 2
    lea rsi, [msg]
    mov edx, MSG_LEN
    syscall
    mov eax, 60
    mov edi, 1
    syscall

section .data
msg: db "access denied", 10
MSG_LEN equ $ - msg

section .bss
buf: resb 4096
