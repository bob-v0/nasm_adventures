; Level 105 — Reentrancy at Await Points (reference)
;
; A bank: 4 accounts, and one task per transfer request. Each transfer checks the
; balance, records the transfer in the audit log (an await: the audit log is slow,
; other tasks run meanwhile), then moves the money. Run alone, every transfer is
; perfect. Under some task schedules the bank creates money, or lets an account go
; negative.
;
; 1. Find a schedule that breaks it:   ;! witness schedule = N
; 2. Fix it.

global _start
extern rt_spawn, rt_run, rt_yield

ACCOUNTS equ 4

section .text
_start:
    xor ebx, ebx
.spawn:
    cmp rbx, [ntransfers]
    jae .run
    lea rdi, [transfer]
    mov rsi, rbx
    call rt_spawn
    inc rbx
    jmp .spawn
.run:
    call rt_run
    xor ebx, ebx                ; "transfer K: ok" / "transfer K: rejected"
.report:
    cmp rbx, [ntransfers]
    jae .balances
    lea rsi, [t_msg]
    call print
    mov rax, rbx
    call print_number
    lea rsi, [ok_msg]
    cmp byte [result + rbx], 1
    je .say
    lea rsi, [no_msg]
.say:
    call print
    inc rbx
    jmp .report
.balances:
    lea rsi, [b_msg]
    call print
    xor ebx, ebx
.balance:
    mov rax, [accounts + rbx*8]
    call print_number
    inc rbx
    lea rsi, [space]
    cmp rbx, ACCOUNTS
    jb .sep
    lea rsi, [newline]
.sep:
    call print
    cmp rbx, ACCOUNTS
    jb .balance
    mov eax, 60
    xor edi, edi
    syscall

transfer:                       ; rdi = which request (from, to, amount at transfers + 24*k)
    push rbx
    push r12
    push r13
    mov rbx, rdi
    imul r12, rdi, 24
    lea r12, [transfers + r12]
    call audit                  ; log it first (await)...
    mov rax, [r12]              ; ...THEN read the balance: nothing awaits between the
    mov r13, [accounts + rax*8] ; check and the update, so no other task can change it
    cmp r13, [r12 + 16]
    jl .reject                  ; not enough money
    sub r13, [r12 + 16]
    mov rax, [r12]
    mov [accounts + rax*8], r13
    mov rax, [r12 + 8]          ; to
    mov rcx, [r12 + 16]
    add [accounts + rax*8], rcx
    mov byte [result + rbx], 1
    jmp .done
.reject:
    mov byte [result + rbx], 2
.done:
    pop r13
    pop r12
    pop rbx
    ret

audit:                          ; the audit log is a slow service: an await point
    sub rsp, 8
    inc qword [audited]
    call rt_yield
    add rsp, 8
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

print_number:                   ; rax = n (signed)
    push rbx
    lea rsi, [digits + 23]
    mov byte [rsi], 0
    mov rbx, rax
    test rax, rax
    jns .positive
    neg rax
.positive:
    mov ecx, 10
.digit:
    xor edx, edx
    div rcx
    add dl, '0'
    dec rsi
    mov [rsi], dl
    test rax, rax
    jnz .digit
    test rbx, rbx
    jns .print
    dec rsi
    mov byte [rsi], '-'
.print:
    pop rbx
    jmp print

section .data
accounts:   dq 1000, 1000, 1000, 1000
ntransfers: dq 3
transfers:  dq 0, 1, 700            ; from, to, amount
            dq 0, 2, 600
            dq 3, 0, 100
            times 3 * 13 dq 0
t_msg:   db "transfer ", 0
ok_msg:  db ": ok", 10, 0
no_msg:  db ": rejected", 10, 0
b_msg:   db "balances: ", 0
space:   db " ", 0
newline: db 10, 0

section .bss
result:  resb 16
audited: resq 1
digits:  resb 24
;! witness schedule = 1
