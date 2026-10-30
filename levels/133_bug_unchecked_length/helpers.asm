; Provided by level 133. An account record: a 16-byte name field, then the balance.
;   ring_rename(): calls set_name(account, input), as the application does when a
;                  customer changes their name.
bits 64
global ring_rename
global account
global input
extern set_name

ACCOUNT_NAME    equ 0
ACCOUNT_BALANCE equ 16

section .text
ring_rename:
    sub rsp, 8
    lea rdi, [account]
    lea rsi, [input]
    call set_name
    add rsp, 8
    ret

section .data
account: times 24 db 0          ; name[16], balance (qword)
input:   times 64 db 0          ; the new name, NUL-terminated
