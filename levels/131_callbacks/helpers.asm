; Provided by level 131: the functions passed to yours, and the pipeline that uses them.
; Like any function, each one may destroy every caller-saved register, and each
; counts calls made with a misaligned stack.
bits 64
global ring_pipeline
global data
global ring_count
global ring_misaligned
global ring_add3, ring_is_odd, ring_add, ring_square, ring_gt10, ring_max
extern map, filter, reduce

%macro CHECK_AND_SCRAMBLE 0
    lea r11, [rsp + 8]
    test r11b, 15
    jz %%ok
    inc qword [ring_misaligned]
%%ok:
    mov rcx, 0x5C5C5C5C5C5C5C5C
    mov rdx, rcx
    mov rsi, rcx
    mov rdi, rcx
    mov r8, rcx
    mov r9, rcx
    mov r10, rcx
    mov r11, rcx
    ret
%endmacro

section .text
ring_add3:      lea rax, [rdi + 3]
                CHECK_AND_SCRAMBLE
ring_is_odd:    mov eax, edi
                and eax, 1
                CHECK_AND_SCRAMBLE
ring_add:       lea rax, [rdi + rsi]
                CHECK_AND_SCRAMBLE
ring_square:    mov rax, rdi
                imul rax, rdi
                CHECK_AND_SCRAMBLE
ring_gt10:      xor eax, eax
                cmp rdi, 10
                seta al
                CHECK_AND_SCRAMBLE
ring_max:       mov rax, rdi
                cmp rsi, rdi
                cmova rax, rsi
                CHECK_AND_SCRAMBLE

ring_pipeline:                  ; rdi = n, rsi = which (0 or 1) -> rax = result
    push rbx
    push r12
    push r13                    ; 3 pushes: aligned
    mov rbx, rdi
    mov r12, rsi
    lea r13, [pipelines + r12*8]
    mov r13, [r13]              ; this pipeline's three functions
    lea rdi, [data]             ; map(data, n, fn)
    mov rsi, rbx
    mov rdx, [r13]
    call map
    lea rdi, [data]             ; n = filter(data, n, pred)
    mov rsi, rbx
    mov rdx, [r13 + 8]
    call filter
    mov rbx, rax
    mov [ring_count], rax
    lea rdi, [data]             ; reduce(data, n, fn, 0)
    mov rsi, rbx
    mov rdx, [r13 + 16]
    xor ecx, ecx
    call reduce
    pop r13
    pop r12
    pop rbx
    ret

section .data
pipeline0: dq ring_add3, ring_is_odd, ring_add
pipeline1: dq ring_square, ring_gt10, ring_max
pipelines: dq pipeline0, pipeline1
data:            times 64 dq 0
ring_count:      dq 0
ring_misaligned: dq 0
