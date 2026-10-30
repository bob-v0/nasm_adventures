; Level 103 — Cancellation Leak (reference)
;
; Workers save job records to a small database: each takes a buffer (rt_malloc), formats
; its record, takes the database lock, "writes to disk" (an await), appends the record,
; then releases the lock and the buffer. A supervisor may cancel any task at any await:
; the await then returns -125 (ECANCELED).
;
; The workers handle cancellation by returning at once. Since then the service
; sometimes freezes (tasks waiting forever) and leaks memory. Make every way out of a
; worker release everything it holds.

global _start
extern rt_spawn, rt_run, rt_lock, rt_unlock, rt_sleep, rt_malloc, rt_free

ECANCELED equ 125

section .text
_start:
    xor ebx, ebx
.spawn:
    cmp rbx, [njobs]
    jae .run
    lea rdi, [worker]
    mov rsi, rbx
    call rt_spawn
    inc rbx
    jmp .spawn
.run:
    call rt_run
    mov r12, rax                ; tasks stuck forever
    lea rsi, [done_msg]         ; "done D, cancelled C, records R"
    call print
    mov rax, [done]
    call print_number
    lea rsi, [cancelled_msg]
    call print
    mov rax, [cancelled]
    call print_number
    lea rsi, [records_msg]
    call print
    mov rax, [records]
    call print_number
    lea rsi, [newline]
    call print
    mov eax, 60
    mov rdi, r12
    syscall

worker:                         ; rdi = job number
    push rbx
    push r12
    sub rsp, 8
    mov r12, rdi
    mov edi, 64
    call rt_malloc              ; a buffer for the record
    mov rbx, rax
    mov rax, r12                ; record: "job N", 10
    mov dword [rbx], 'job '
    add al, '0'
    mov [rbx + 4], al
    mov byte [rbx + 5], 10
    lea rdi, [db_lock]
    call rt_lock                ; await: wait for the database
    cmp rax, -ECANCELED
    je .cancelled               ; (cancelled while waiting: we don't hold the lock)
    mov edi, 2
    call rt_sleep               ; await: the disk is slow
    cmp rax, -ECANCELED
    je .cancelled_locked
    mov rax, [db_len]           ; append the record
    mov rcx, [rbx]
    mov [db + rax], rcx
    add qword [db_len], 6
    inc qword [records]
    lea rdi, [db_lock]
    call rt_unlock
    mov rdi, rbx
    call rt_free
    inc qword [done]
    jmp .out
.cancelled_locked:              ; every way out releases what it holds
    lea rdi, [db_lock]
    call rt_unlock
.cancelled:
    mov rdi, rbx
    call rt_free
    inc qword [cancelled]
.out:
    add rsp, 8
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

print_number:                   ; rax = n
    lea rsi, [digits + 23]
    mov byte [rsi], 0
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
njobs:         dq 4
done_msg:      db "done ", 0
cancelled_msg: db ", cancelled ", 0
records_msg:   db ", records ", 0
newline:       db 10, 0

section .bss
db_lock:   resq 3
db_len:    resq 1
db:        resb 1024
done:      resq 1
cancelled: resq 1
records:   resq 1
digits:    resb 24
