; A first-fit free-list allocator with splitting.
; Block header (16 bytes): [0] block size including the header, [8] next free block.
global malloc
global free

MIN_SPLIT equ 64

section .text
malloc:                             ; rdi = size
    lea rax, [rdi + 15 + 16]
    and rax, -16                    ; needed = round16(size) + header
    mov rsi, rax
    lea rdx, [free_list]            ; rdx = address of the link pointing at rcx
    mov rcx, [free_list]
.search:
    test rcx, rcx
    jz .grow
    cmp [rcx], rsi
    jae .found
    lea rdx, [rcx + 8]
    mov rcx, [rcx + 8]
    jmp .search
.found:
    mov rax, [rcx]
    sub rax, rsi                    ; leftover
    cmp rax, MIN_SPLIT
    jb .take_whole
    lea r8, [rcx + rsi]             ; split: the tail becomes a new free block
    mov [r8], rax
    mov r9, [rcx + 8]
    mov [r8 + 8], r9
    mov [rdx], r8
    mov [rcx], rsi
    jmp .ret_block
.take_whole:
    mov r9, [rcx + 8]
    mov [rdx], r9                   ; unlink
.ret_block:
    lea rax, [rcx + 16]
    ret
.grow:
    mov rcx, [heap_end]
    test rcx, rcx
    jnz .have_end
    push rsi
    mov eax, 12                     ; brk(0): where the heap starts
    xor edi, edi
    syscall
    pop rsi
    add rax, 15
    and rax, -16
    mov rcx, rax
.have_end:
    lea rdi, [rcx + rsi]
    push rcx
    push rsi
    mov eax, 12                     ; brk(end + needed)
    syscall
    pop rsi
    pop rcx
    lea rdi, [rcx + rsi]
    cmp rax, rdi
    jb .out_of_memory
    mov [heap_end], rdi
    mov [rcx], rsi
    lea rax, [rcx + 16]
    ret
.out_of_memory:
    xor eax, eax
    ret

free:                               ; rdi = pointer
    test rdi, rdi
    jz .done
    lea rcx, [rdi - 16]             ; header
    mov rax, [free_list]
    mov [rcx + 8], rax              ; push onto the free list
    mov [free_list], rcx
.done:
    ret

section .data
free_list: dq 0
heap_end:  dq 0
