struc Person
    .next:  resq 1
    .age:   resd 1
    .flags: resb 1
            resb 3                  ; padding
    .name:  resb 16
endstruc

    mov rax, [head]
    mov [newbie + Person.next], rax ; newbie -> old first record
    mov r8, newbie
    mov [head], r8

    xor eax, eax                    ; count
    xor ebx, ebx                    ; sum of ages
    xor edx, edx                    ; flagged
    mov rcx, r8                     ; oldest so far
    mov r10d, [r8 + Person.age]     ; its age
    mov rsi, r8
.walk:
    test rsi, rsi
    jz .done
    inc rax
    mov r9d, [rsi + Person.age]     ; dword load zero-extends
    add rbx, r9
    cmp r9d, r10d
    jbe .not_older                  ; strictly older only: ties keep the first
    mov r10d, r9d
    mov rcx, rsi
.not_older:
    test byte [rsi + Person.flags], 1
    jz .advance
    inc rdx
.advance:
    mov rsi, [rsi + Person.next]
    jmp .walk
.done:

section .data
newbie: istruc Person
    at Person.age,   dd 99
    at Person.flags, db 1
    at Person.name,  db "zed", 0
iend
