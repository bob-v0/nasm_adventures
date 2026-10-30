CLOCK_MONOTONIC equ 1
GAP_NS          equ 400_000_000

global _start

section .text
_start:
    call now
    mov r12, rax                    ; t0
    mov eax, 35                     ; nanosleep(1.25 s)
    lea rdi, [nap]
    xor esi, esi
    syscall
    call now
    sub rax, r12
    xor edx, edx
    mov ecx, 1_000_000
    div rcx                         ; ms
    call print_slept

    xor r13d, r13d                  ; read all of stdin
.read:
    xor eax, eax
    xor edi, edi
    lea rsi, [input + r13]
    mov edx, 8192
    sub rdx, r13
    syscall
    test rax, rax
    jle .lines
    add r13, rax
    jmp .read
.lines:
    xor r14d, r14d                  ; position
    xor r15d, r15d                  ; time of the last line (0 = none yet)
.line:
    cmp r14, r13
    jae .done
    mov rbx, r14                    ; start of the line
.find:
    cmp byte [input + r14], 10
    je .found
    inc r14
    cmp r14, r13
    jb .find
    dec r14
.found:
    inc r14                         ; one past the newline
    test r15, r15
    jz .write
    call now
    mov rcx, rax
    sub rcx, r15                    ; elapsed since the last line
    cmp rcx, GAP_NS
    jae .write
    mov rax, GAP_NS
    sub rax, rcx                    ; sleep for the rest
    xor edx, edx
    mov ecx, 1_000_000_000
    div rcx
    mov [ts], rax
    mov [ts + 8], rdx
    mov eax, 35
    lea rdi, [ts]
    xor esi, esi
    syscall
.write:
    mov eax, 1
    mov edi, 1
    lea rsi, [input + rbx]
    mov rdx, r14
    sub rdx, rbx
    syscall
    call now
    mov r15, rax
    jmp .line
.done:
    mov eax, 60
    xor edi, edi
    syscall

now:                                ; -> rax = monotonic time in ns
    mov eax, 228
    mov edi, CLOCK_MONOTONIC
    lea rsi, [ts]
    syscall
    imul rax, [ts], 1_000_000_000
    add rax, [ts + 8]
    ret

print_slept:                        ; rax = ms
    lea rsi, [num + 20]
    mov ecx, 10
.digit:
    xor edx, edx
    div rcx
    add dl, '0'
    dec rsi
    mov [rsi], dl
    test rax, rax
    jnz .digit
    sub rsi, 6                      ; "slept " in front of the digits
    mov dword [rsi], 'slep'
    mov word [rsi + 4], 't '
    lea rdx, [num + 24]
    sub rdx, rsi
    mov eax, 1
    mov edi, 1
    syscall
    ret

section .data
nap: dq 1, 250_000_000
num: times 20 db 0
     db " ms", 10

section .bss
ts:    resq 2
input: resb 8192
