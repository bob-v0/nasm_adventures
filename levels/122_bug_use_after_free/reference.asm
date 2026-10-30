; Level 122 — reference fix
;
; dedupe: reads words from stdin (one per line), keeps them in a linked list,
; removes repeated words (keeping the first), prints what's left in order, and
; frees everything. Node: [0] next, [8] length, [16] the word's bytes.
;
; Its output is right. Under the game's checked allocator it is stopped on the spot.
; Fix both bugs, changing at most 6 lines.

extern malloc
extern free
global _start

section .text
_start:
    call read_all
    call build_list
    call dedupe
    call print_list
    call free_all
    mov eax, 60
    xor edi, edi
    syscall

dedupe:                             ; remove later copies of every word
    push r12
    push r13
    push r14
    mov r12, [head]
.outer:
    test r12, r12
    jz .done
    mov r13, r12                    ; r13 = the node before the candidate
.inner:
    mov r14, [r13]                  ; candidate = r13->next
    test r14, r14
    jz .next_outer
    mov rdi, r12
    mov rsi, r14
    call same_word
    test eax, eax
    jz .keep
    mov rax, [r14]                  ; fix: unlink it first...
    mov [r13], rax
    mov rdi, r14                    ; ...then free it
    call free
    jmp .inner
.keep:
    mov r13, r14
    jmp .inner
.next_outer:
    mov r12, [r12]
    jmp .outer
.done:
    pop r14
    pop r13
    pop r12
    ret

free_all:
    push r12
    mov r12, [head]
.next:
    test r12, r12
    jz .done
    mov rdi, r12
    mov r12, [r12]                  ; fix: read next before freeing
    call free
    jmp .next
.done:
    mov qword [head], 0
    pop r12
    ret

; ---- the rest works as intended -----------------------------------------------------

read_all:                           ; stdin -> input, length in [input_len]
    xor r8d, r8d
.more:
    xor eax, eax
    xor edi, edi
    lea rsi, [input + r8]
    mov edx, 4096
    sub rdx, r8
    jz .done
    syscall
    test rax, rax
    jle .done
    add r8, rax
    jmp .more
.done:
    mov [input_len], r8
    ret

build_list:                         ; one node per non-empty line, in order
    push rbx
    push r12
    push r13
    push r14
    push r15
    lea r15, [head]                 ; where to store the next node's address
    xor r12d, r12d                  ; position in input
.line:
    cmp r12, [input_len]
    jae .done
    mov r13, r12                    ; start of the word
.scan:
    cmp r12, [input_len]
    jae .word
    cmp byte [input + r12], 10
    je .word
    inc r12
    jmp .scan
.word:
    mov r14, r12
    sub r14, r13                    ; length
    inc r12                         ; skip the newline
    test r14, r14
    jz .line
    lea rdi, [r14 + 16]
    call malloc
    mov qword [rax], 0
    mov [rax + 8], r14
    lea rsi, [input + r13]
    lea rdi, [rax + 16]
    mov rcx, r14
    rep movsb
    mov [r15], rax
    mov r15, rax                    ; next link goes in this node
    jmp .line
.done:
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

same_word:                          ; rdi, rsi = nodes -> eax = 1 if equal
    xor eax, eax
    mov rcx, [rdi + 8]
    cmp rcx, [rsi + 8]
    jne .no
    lea rdi, [rdi + 16]
    lea rsi, [rsi + 16]
    repe cmpsb
    jne .no
    mov eax, 1
.no:
    ret

print_list:
    push r12
    mov r12, [head]
.next:
    test r12, r12
    jz .done
    mov eax, 1
    mov edi, 1
    lea rsi, [r12 + 16]
    mov rdx, [r12 + 8]
    syscall
    mov eax, 1
    mov edi, 1
    lea rsi, [newline]
    mov edx, 1
    syscall
    mov r12, [r12]
    jmp .next
.done:
    pop r12
    ret

section .data
newline: db 10
head:    dq 0

section .bss
input:     resb 4096
input_len: resq 1
