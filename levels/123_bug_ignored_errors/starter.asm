; Level 123 — Bug: Ignored Errors
;
; backup: copy /work/config.txt to /work/config.bak, then print
; "backed up N bytes". On any failure it must print one line to stderr and exit 1:
;     backup: cannot open config.txt
;     backup: cannot create config.bak
;     backup: read error
;     backup: write error
; and it must close every file it opened (on every path).
;
; It "works" on the author's machine. Fix its error handling.
; At most 10 changed lines.

global _start

section .text
_start:
    mov eax, 2                      ; open("config.txt", O_RDONLY)
    lea rdi, [src_name]
    xor esi, esi
    syscall
    cmp rax, 0
    je .no_source
    mov r12, rax
    mov eax, 2                      ; open("config.bak", O_WRONLY|O_CREAT|O_TRUNC, 0600)
    lea rdi, [dst_name]
    mov esi, 1 | 0o100 | 0o1000
    mov edx, 0o600
    syscall
    mov r13, rax
    xor r14d, r14d                  ; bytes copied
.copy:
    xor eax, eax                    ; read(src, buf, 4096)
    mov rdi, r12
    lea rsi, [buf]
    mov edx, 4096
    syscall
    test rax, rax
    jz .copied
    mov r15, rax
    mov eax, 1                      ; write(dst, buf, n)
    mov rdi, r13
    lea rsi, [buf]
    mov rdx, r15
    syscall
    add r14, r15
    jmp .copy
.copied:
    call close_both
    mov rdi, r14
    call report
    mov eax, 60
    xor edi, edi
    syscall

.no_source:
    lea rsi, [msg_open]
    mov edx, MSG_OPEN_LEN
    jmp fail
.no_dest:
    lea rsi, [msg_create]
    mov edx, MSG_CREATE_LEN
    jmp fail
.read_error:
    lea rsi, [msg_read]
    mov edx, MSG_READ_LEN
    jmp fail
.write_error:
    lea rsi, [msg_write]
    mov edx, MSG_WRITE_LEN
    jmp fail

fail:                               ; rsi, rdx = message: print it, exit(1)
    mov eax, 1
    mov edi, 2
    syscall
    mov eax, 60
    mov edi, 1
    syscall

fail_closing:                       ; the same, after closing both files
    push rsi
    push rdx
    call close_both
    pop rdx
    pop rsi
    jmp fail

close_both:
    mov eax, 3
    mov rdi, r12
    syscall
    mov eax, 3
    mov rdi, r13
    syscall
    ret

report:                             ; print "backed up <rdi> bytes\n"
    lea rsi, [num + 20]
    mov rax, rdi
    mov ecx, 10
.digit:
    xor edx, edx
    div rcx
    add dl, '0'
    dec rsi
    mov [rsi], dl
    test rax, rax
    jnz .digit
    sub rsi, PREFIX_LEN
    mov rdi, rsi                    ; copy the prefix in front of the digits
    lea r8, [prefix]
    mov ecx, PREFIX_LEN
.prefix:
    mov al, [r8]
    mov [rdi], al
    inc r8
    inc rdi
    dec ecx
    jnz .prefix
    lea rdx, [num + 20 + SUFFIX_LEN]
    sub rdx, rsi
    mov eax, 1
    mov edi, 1
    syscall
    ret

section .data
src_name:   db "config.txt", 0
dst_name:   db "config.bak", 0
msg_open:   db "backup: cannot open config.txt", 10
MSG_OPEN_LEN equ $ - msg_open
msg_create: db "backup: cannot create config.bak", 10
MSG_CREATE_LEN equ $ - msg_create
msg_read:   db "backup: read error", 10
MSG_READ_LEN equ $ - msg_read
msg_write:  db "backup: write error", 10
MSG_WRITE_LEN equ $ - msg_write
prefix:     db "backed up "
PREFIX_LEN equ $ - prefix
            times 20 - PREFIX_LEN db 0
num:        times 20 db 0
            db " bytes", 10
SUFFIX_LEN equ 7

section .bss
buf: resb 4096
