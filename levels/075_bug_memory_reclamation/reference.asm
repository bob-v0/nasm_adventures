; Level 75 — Memory Reclamation (reference)
;
; Level 77's lock-free stack, with nodes from the heap: four threads each allocate and
; push 30 values, and pop and free nodes as they go; the main thread frees what's left.
; Under some schedules the game's checked allocator stops it: "use after free".
;
; 1. Find such a schedule:   ;! witness schedule = N
; 2. Fix it: a node may only be freed once no thread can still be reading it. (Hint:
;    hazard pointers. Every node must still be freed by the end.)

global _start

THREADS equ 4
ROUNDS  equ 30
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000
SYS_MALLOC equ 0x1000           ; the game's checked allocator
SYS_FREE   equ 0x1001
; a node: dq next, dq value

section .text
_start:
    xor ebx, ebx
.spawn:
    cmp ebx, THREADS
    je .join
    mov r12, rbx                ; my thread number
    mov eax, 56
    mov edi, CLONE
    lea rsi, [rbx + 1]
    shl rsi, 13
    lea rsi, [stacks + rsi]
    lea rdx, [tids + rbx*4]
    mov r10, rdx
    xor r8d, r8d
    syscall
    test rax, rax
    jz worker
    inc ebx
    jmp .spawn
.join:
    xor ebx, ebx
.next:
    cmp ebx, THREADS
    je .drain
.wait:
    mov edx, [tids + rbx*4]
    test edx, edx
    jz .joined
    mov eax, 202
    lea rdi, [tids + rbx*4]
    xor esi, esi
    xor r10d, r10d
    syscall
    jmp .wait
.joined:
    inc ebx
    jmp .next
.drain:                         ; everyone's gone: free what's left, retired ones too
    xor ebx, ebx
.retired:
    mov rdi, rbx
    xor esi, esi                ; (nobody holds hazards any more)
    call scan
    inc ebx
    cmp ebx, THREADS
    jb .retired
.rest:
    mov rdi, r12
    call pop
    test rax, rax
    jz .done
    mov rdi, rax
    call free
    jmp .rest
.done:
    mov eax, 1
    mov edi, 1
    lea rsi, [msg]
    mov edx, MSG_LEN
    syscall
    mov eax, 231
    xor edi, edi
    syscall

worker:                         ; r12 = me
    mov r13d, ROUNDS
.round:
    mov edi, 16
    call malloc
    mov [rax + 8], r13          ; a value
    mov rsi, rax
    call push
    mov rdi, r12
    call pop
    test rax, rax
    jz .again
    mov rdi, r12                ; done with it, but someone may still be reading it:
    mov rsi, rax                ; retire it instead of freeing it
    call retire
.again:
    dec r13d
    jnz .round
    mov eax, 60
    xor edi, edi
    syscall

; ---- the stack ----------------------------------------------------------------------

push:                           ; rsi = node
    mov rax, [top]
.retry:
    mov [rsi], rax
    lock cmpxchg [top], rsi
    jnz .retry
    ret

pop:                            ; rdi = my thread number -> rax = node or 0
    shl rdi, 6
    lea rcx, [hazards + rdi]    ; my hazard slot
.retry:
    mov rax, [top]
    test rax, rax
    jz .empty
    mov [rcx], rax              ; "I'm about to read this node: don't free it"
    mfence                      ; (visible before I look at top again)
    cmp rax, [top]              ; still the top? then nobody had freed it before my
    jne .retry                  ; hazard was visible, and nobody will now
    mov rdx, [rax]              ; top.next: safe to read
    lock cmpxchg [top], rdx
    jnz .retry
.empty:
    mov qword [rcx], 0          ; done looking
    ret

; Retired nodes wait in a per-thread list until no hazard pointer names them.
RETIRE_MAX equ 16
SCAN_AT    equ 8

retire:                         ; rdi = me, rsi = node
    mov rax, rdi
    shl rax, 7                  ; 16 qwords per thread
    mov rcx, [nretired + rdi*8]
    lea rdx, [retired + rax]
    mov [rdx + rcx*8], rsi
    inc rcx
    mov [nretired + rdi*8], rcx
    cmp rcx, SCAN_AT
    jb .done
    mov esi, 1
    jmp scan
.done:
    ret

scan:                           ; rdi = thread, esi = 1: respect hazards / 0: free all
    push rbx
    push r12
    push r13
    push r14
    push r15
    mov r15d, esi
    mov r12, rdi
    mov rax, rdi
    shl rax, 7
    lea r13, [retired + rax]    ; its list
    xor ebx, ebx                ; read index
    xor r14d, r14d              ; kept
.each:
    cmp rbx, [nretired + r12*8]
    jae .finished
    mov rdi, [r13 + rbx*8]
    inc rbx
    test r15d, r15d
    jz .free
    xor ecx, ecx                ; is it anyone's hazard?
.hazard:
    mov rax, rcx
    shl rax, 6
    cmp [hazards + rax], rdi
    je .keep
    inc ecx
    cmp ecx, THREADS
    jb .hazard
.free:
    call free
    jmp .each
.keep:
    mov [r13 + r14*8], rdi
    inc r14
    jmp .each
.finished:
    mov [nretired + r12*8], r14
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

; ---- the heap -------------------------------------------------------------------------

malloc:                         ; rdi = size -> rax
    mov eax, SYS_MALLOC
    syscall
    ret

free:                           ; rdi = block
    mov eax, SYS_FREE
    syscall
    ret

section .data
msg: db "done", 10
MSG_LEN equ $ - msg

section .bss
alignb 64
top:     resq 8
hazards: resq 8 * THREADS       ; one cache line per thread, zeroed (yours to use)
nretired: resq THREADS
retired:  resq 16 * THREADS
tids:    resd THREADS
alignb 16
stacks:  resb (THREADS + 1) * 8192
;! witness schedule = 0
