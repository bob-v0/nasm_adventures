; Level 116 — Time of Check, Time of Use (reference)
;
; The original checked the NAME with access(), then opened the NAME: between the two,
; the name can start pointing somewhere else. The fix opens first, then checks the
; file it actually got, with fstat. (No name lookup happens after the check.)

global _start

section .text
_start:
    mov rbx, [rsp + 16]         ; PATH = argv[1]
    mov eax, 2                  ; open(PATH, O_RDONLY): first get the file...
    mov rdi, rbx
    xor esi, esi
    syscall
    test rax, rax
    js denied
    mov r12, rax
    mov eax, 5                  ; ...then check THAT file: fstat(fd, &st)
    mov rdi, r12
    lea rsi, [st]
    syscall
    cmp dword [st + 28], 1000   ; st_uid: the user's own file?
    je copy
    test dword [st + 24], 4     ; st_mode: readable by everyone?
    jz refuse
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
refuse:
    mov eax, 3
    mov rdi, r12
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
st:  resb 144
;! witness after = "access"
