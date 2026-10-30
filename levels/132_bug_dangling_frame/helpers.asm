; Provided by level 132.
;   ring_report(a, b, c, d): formats the pairs (a, b) and (c, d) with your
;   format_pair into two buffers it owns, does some other work (ring_scrub, which
;   uses the stack like any function), then copies both texts into `report`, one
;   per line. Returns the report's length.
bits 64
global ring_report
global report
extern format_pair

section .text
ring_report:                    ; rdi = a, rsi = b, rdx = c, rcx = d
    push rbx
    push r12
    push r13
    push r14
    push r15                    ; 5 pushes: aligned
    mov r12, rdx
    mov r13, rcx
    lea rdx, [buf1]             ; format_pair(a, b, buf1)
    call format_pair
    mov r14, rax
    mov rdi, r12                ; format_pair(c, d, buf2)
    mov rsi, r13
    lea rdx, [buf2]
    call format_pair
    mov r15, rax
    call ring_scrub
    lea rbx, [report]
    mov rsi, r14
    call append_line
    mov rsi, r15
    call append_line
    mov byte [rbx], 0
    lea rax, [report]
    sub rbx, rax
    mov rax, rbx
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

append_line:                    ; copy the C string at rsi (at most 48 bytes) to rbx, then '\n'
    mov ecx, 48
.copy:
    mov al, [rsi]
    test al, al
    jz .end
    mov [rbx], al
    inc rbx
    inc rsi
    dec ecx
    jnz .copy
.end:
    mov byte [rbx], 10
    inc rbx
    ret

ring_scrub:                     ; other work: uses 512 bytes of stack
    sub rsp, 520
    mov rdi, rsp
    mov ecx, 512
    mov al, 0xEE
    rep stosb
    add rsp, 520
    ret

section .data
buf1:   times 48 db 0
buf2:   times 48 db 0
report: times 128 db 0
