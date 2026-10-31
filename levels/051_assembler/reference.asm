; Level 51 — Assembler (reference)
;
; Two passes over the source. Every instruction's size depends only on the instruction
; itself (jumps are always rel32; immediates and displacements are as short as their
; values allow), so pass 1 can record each label's address and pass 2 emits the same
; bytes with every label known.
;
; An operand is parsed into a record (OP_* offsets): its kind, register, width, size
; keyword, and for memory base/index/scale/displacement or a rip-relative target.

global _start

K_REG   equ 1
K_MEM   equ 2
K_IMM   equ 3
NONE    equ 0xFF

OP_KIND  equ 0
OP_REG   equ 1          ; register number (K_REG)
OP_WIDE  equ 2          ; 1: a 64-bit register
OP_SIZE  equ 3          ; 8 / 4 from qword / dword, 0 if none
OP_BASE  equ 4          ; NONE or a register
OP_INDEX equ 5
OP_SCALE equ 6          ; log2 of the scale
OP_RIP   equ 7          ; 1: [rel target]
OP_VALUE equ 8          ; immediate, displacement, or rip target
OP_LEN   equ 16

section .rodata
; mnemonics: 8 bytes of name (NUL-padded), then kind, code
mnemonics:
    db "add", 0, 0, 0, 0, 0, 1, 0
    db "or", 0, 0, 0, 0, 0, 0, 1, 1
    db "and", 0, 0, 0, 0, 0, 1, 4
    db "sub", 0, 0, 0, 0, 0, 1, 5
    db "xor", 0, 0, 0, 0, 0, 1, 6
    db "cmp", 0, 0, 0, 0, 0, 1, 7
    db "mov", 0, 0, 0, 0, 0, 2, 0
    db "test", 0, 0, 0, 0, 3, 0
    db "lea", 0, 0, 0, 0, 0, 4, 0
    db "inc", 0, 0, 0, 0, 0, 5, 0
    db "dec", 0, 0, 0, 0, 0, 5, 1
    db "push", 0, 0, 0, 0, 6, 0x50
    db "pop", 0, 0, 0, 0, 0, 6, 0x58
    db "jmp", 0, 0, 0, 0, 0, 8, 0
    db "call", 0, 0, 0, 0, 9, 0
    db "ret", 0, 0, 0, 0, 0, 10, 0xC3
    db "nop", 0, 0, 0, 0, 0, 10, 0x90
    db "syscall", 0, 11, 0
    db "jo", 0, 0, 0, 0, 0, 0, 7, 0
    db "jno", 0, 0, 0, 0, 0, 7, 1
    db "jb", 0, 0, 0, 0, 0, 0, 7, 2
    db "jae", 0, 0, 0, 0, 0, 7, 3
    db "je", 0, 0, 0, 0, 0, 0, 7, 4
    db "jne", 0, 0, 0, 0, 0, 7, 5
    db "jbe", 0, 0, 0, 0, 0, 7, 6
    db "ja", 0, 0, 0, 0, 0, 0, 7, 7
    db "js", 0, 0, 0, 0, 0, 0, 7, 8
    db "jns", 0, 0, 0, 0, 0, 7, 9
    db "jp", 0, 0, 0, 0, 0, 0, 7, 10
    db "jnp", 0, 0, 0, 0, 0, 7, 11
    db "jl", 0, 0, 0, 0, 0, 0, 7, 12
    db "jge", 0, 0, 0, 0, 0, 7, 13
    db "jle", 0, 0, 0, 0, 0, 7, 14
    db "jg", 0, 0, 0, 0, 0, 0, 7, 15
    dq 0
; registers: 8 bytes of name, then number, width
registers:
    db "rax", 0, 0, 0, 0, 0, 0, 1,  "rcx", 0, 0, 0, 0, 0, 1, 1
    db "rdx", 0, 0, 0, 0, 0, 2, 1,  "rbx", 0, 0, 0, 0, 0, 3, 1
    db "rsp", 0, 0, 0, 0, 0, 4, 1,  "rbp", 0, 0, 0, 0, 0, 5, 1
    db "rsi", 0, 0, 0, 0, 0, 6, 1,  "rdi", 0, 0, 0, 0, 0, 7, 1
    db "r8", 0, 0, 0, 0, 0, 0, 8, 1,  "r9", 0, 0, 0, 0, 0, 0, 9, 1
    db "r10", 0, 0, 0, 0, 0, 10, 1, "r11", 0, 0, 0, 0, 0, 11, 1
    db "r12", 0, 0, 0, 0, 0, 12, 1, "r13", 0, 0, 0, 0, 0, 13, 1
    db "r14", 0, 0, 0, 0, 0, 14, 1, "r15", 0, 0, 0, 0, 0, 15, 1
    db "eax", 0, 0, 0, 0, 0, 0, 0,  "ecx", 0, 0, 0, 0, 0, 1, 0
    db "edx", 0, 0, 0, 0, 0, 2, 0,  "ebx", 0, 0, 0, 0, 0, 3, 0
    db "esp", 0, 0, 0, 0, 0, 4, 0,  "ebp", 0, 0, 0, 0, 0, 5, 0
    db "esi", 0, 0, 0, 0, 0, 6, 0,  "edi", 0, 0, 0, 0, 0, 7, 0
    db "r8d", 0, 0, 0, 0, 0, 8, 0,  "r9d", 0, 0, 0, 0, 0, 9, 0
    db "r10d", 0, 0, 0, 0, 10, 0,   "r11d", 0, 0, 0, 0, 11, 0
    db "r12d", 0, 0, 0, 0, 12, 0,   "r13d", 0, 0, 0, 0, 13, 0
    db "r14d", 0, 0, 0, 0, 14, 0,   "r15d", 0, 0, 0, 0, 15, 0
    dq 0
qword_kw: db "qword "
dword_kw: db "dword "

section .bss
src:     resb 65536
srclen:  resq 1
out:     resb 65536
pass:    resb 1
name:    resb 32            ; the last identifier read, NUL-padded
nlabels: resq 1
labels:  resb 512 * 32      ; 24 bytes of name, 8 of address
ops:     resb 2 * OP_LEN
rip_at:  resq 1             ; where the current instruction's rip disp32 is (0: none)
rip_to:  resq 1

section .text
_start:
    xor ebx, ebx                ; bytes read
.read:
    xor eax, eax
    xor edi, edi
    lea rsi, [rel src]
    add rsi, rbx
    mov edx, 65535
    sub edx, ebx
    jz .read_done
    syscall
    test rax, rax
    jle .read_done
    add rbx, rax
    jmp .read
.read_done:
    mov [rel srclen], rbx
    mov byte [rel pass], 1
    call assemble
    mov byte [rel pass], 2
    call assemble
    mov eax, 1                  ; write the machine code
    mov edi, 1
    lea rsi, [rel out]
    mov rdx, r15
    syscall
    mov eax, 60
    xor edi, edi
    syscall

; one pass: r12 = the parse cursor, r13 = the end of the line, r15 = bytes emitted
assemble:
    xor r15d, r15d
    lea r12, [rel src]
    lea r14, [rel src]
    add r14, [rel srclen]       ; the end of the source
.line:
    cmp r12, r14
    jae .done
    mov r13, r12
.find_end:
    cmp r13, r14
    jae .have_line
    cmp byte [r13], 10
    je .have_line
    inc r13
    jmp .find_end
.have_line:
    call do_line
    lea r12, [r13 + 1]
    jmp .line
.done:
    ret

do_line:
    call skip_spaces
    cmp r12, r13
    jae .ret                    ; empty
    call read_word
    cmp r12, r13
    jae .instruction
    cmp byte [r12], ':'
    jne .instruction
    cmp byte [rel pass], 1      ; a label: remember its address in pass 1
    jne .ret
    mov rax, [rel nlabels]
    inc qword [rel nlabels]
    shl rax, 5
    lea rdi, [rel labels]
    add rdi, rax
    mov rcx, [rel name]
    mov [rdi], rcx
    mov rcx, [rel name + 8]
    mov [rdi + 8], rcx
    mov rcx, [rel name + 16]
    mov [rdi + 16], rcx
    mov [rdi + 24], r15
.ret:
    ret
.instruction:
    lea rsi, [rel mnemonics]
    mov rax, [rel name]
.find:
    mov rdx, [rsi]
    test rdx, rdx
    jz .ret                     ; unknown: ignore
    cmp rdx, rax
    je .found
    add rsi, 10
    jmp .find
.found:
    movzx ebx, byte [rsi + 8]   ; kind
    movzx ebp, byte [rsi + 9]   ; code
    mov qword [rel rip_at], 0
    lea rdi, [rel ops]          ; up to two operands
    call operand
    call skip_spaces
    cmp r12, r13
    jae .operands_done
    cmp byte [r12], ','
    jne .operands_done
    inc r12
    lea rdi, [rel ops + OP_LEN]
    call operand
.operands_done:
    lea rsi, [rel ops]
    lea rdi, [rel ops + OP_LEN]
    cmp ebx, 1
    je i_alu
    cmp ebx, 2
    je i_mov
    cmp ebx, 3
    je i_test
    cmp ebx, 4
    je i_lea
    cmp ebx, 5
    je i_incdec
    cmp ebx, 6
    je i_pushpop
    cmp ebx, 7
    je i_jcc
    cmp ebx, 8
    je i_jmp
    cmp ebx, 9
    je i_call
    cmp ebx, 10
    je i_simple
    mov al, 0x0F                ; syscall
    call emit8
    mov al, 0x05
    jmp emit8

; ---- instructions: rsi = operand 0, rdi = operand 1, ebp = code -----------------------

i_alu:
    cmp byte [rdi + OP_KIND], K_IMM
    je .imm
    cmp byte [rsi + OP_KIND], K_REG
    jne .to_rm
    lea eax, [rbp*8 + 3]        ; reg <- r/m
    movzx edx, byte [rsi + OP_REG]
    movzx ecx, byte [rsi + OP_WIDE]
    mov rsi, rdi
    call encode
    jmp finish
.to_rm:
    lea eax, [rbp*8 + 1]        ; r/m <- reg
    movzx edx, byte [rdi + OP_REG]
    movzx ecx, byte [rdi + OP_WIDE]
    call encode
    jmp finish
.imm:
    mov edx, ebp                ; /n
    call width_of_rm
    mov r8, [rdi + OP_VALUE]
    movsx rax, r8b
    cmp rax, r8
    jne .imm32
    push r8                     ; (encode uses r8)
    mov eax, 0x83
    call encode
    pop rax
    call emit8
    jmp finish
.imm32:
    push r8
    mov eax, 0x81
    call encode
    pop rax
    call emit32
    jmp finish

i_mov:
    cmp byte [rdi + OP_KIND], K_IMM
    je .imm
    cmp byte [rsi + OP_KIND], K_REG
    jne .to_rm
    mov eax, 0x8B
    movzx edx, byte [rsi + OP_REG]
    movzx ecx, byte [rsi + OP_WIDE]
    mov rsi, rdi
    call encode
    jmp finish
.to_rm:
    mov eax, 0x89
    movzx edx, byte [rdi + OP_REG]
    movzx ecx, byte [rdi + OP_WIDE]
    call encode
    jmp finish
.imm:
    mov r8, [rdi + OP_VALUE]
    cmp byte [rsi + OP_KIND], K_REG
    jne .mem_imm
    movzx edx, byte [rsi + OP_REG]
    movzx ecx, byte [rsi + OP_WIDE]
    mov eax, edx                ; REX: W, B
    shr eax, 3
    shl ecx, 3
    or eax, ecx
    jz .no_rex
    or al, 0x40
    call emit8
.no_rex:
    mov eax, edx
    and eax, 7
    or eax, 0xB8                ; B8+r
    call emit8
    cmp byte [rsi + OP_WIDE], 0
    je .imm32
    mov rax, r8
    jmp emit64
.imm32:
    mov eax, r8d
    jmp emit32
.mem_imm:
    mov eax, 0xC7               ; C7 /0 id
    xor edx, edx
    call width_of_rm
    push r8
    call encode
    pop rax
    call emit32
    jmp finish

i_test:
    mov eax, 0x85
    movzx edx, byte [rdi + OP_REG]
    movzx ecx, byte [rdi + OP_WIDE]
    call encode
    jmp finish

i_lea:
    mov eax, 0x8D
    movzx edx, byte [rsi + OP_REG]
    movzx ecx, byte [rsi + OP_WIDE]
    mov rsi, rdi
    call encode
    jmp finish

i_incdec:
    mov eax, 0xFF
    mov edx, ebp
    call width_of_rm
    call encode
    jmp finish

i_pushpop:
    movzx edx, byte [rsi + OP_REG]
    cmp edx, 8
    jb .short
    mov al, 0x41                ; REX.B
    call emit8
.short:
    and edx, 7
    lea eax, [rbp + rdx]
    jmp emit8

i_jcc:
    mov al, 0x0F
    call emit8
    lea eax, [rbp + 0x80]
    jmp rel32
i_jmp:
    mov eax, 0xE9
    jmp rel32
i_call:
    mov eax, 0xE8
rel32:                          ; the opcode's last byte in al, then target − end
    call emit8
    mov rax, [rsi + OP_VALUE]
    sub rax, r15
    sub rax, 4
    jmp emit32

i_simple:
    mov eax, ebp
    jmp emit8

width_of_rm:                    ; ecx = 1 if operand 0 (rsi) is 64-bit (a register or qword)
    movzx ecx, byte [rsi + OP_WIDE]
    cmp byte [rsi + OP_KIND], K_REG
    je .done
    xor ecx, ecx
    cmp byte [rsi + OP_SIZE], 8
    jne .done
    mov ecx, 1
.done:
    ret

; ---- encoding -----------------------------------------------------------------------

; REX, the opcode (al), ModRM with reg = edx and r/m = the operand at rsi, SIB, disp.
; ecx = REX.W. For a rip-relative operand, call `finish` after any immediate.
encode:
    push rax
    mov r9d, edx                ; reg
    mov r10d, ecx
    shl r10d, 3                 ; W
    mov eax, edx
    shr eax, 3
    shl eax, 2
    or r10d, eax                ; R
    cmp byte [rsi + OP_KIND], K_REG
    jne .mem_rex
    movzx eax, byte [rsi + OP_REG]
    shr eax, 3
    or r10d, eax                ; B
    jmp .rex
.mem_rex:
    cmp byte [rsi + OP_RIP], 0
    jne .rex
    movzx eax, byte [rsi + OP_INDEX]
    cmp eax, NONE
    je .no_x
    shr eax, 3
    shl eax, 1
    or r10d, eax                ; X
.no_x:
    movzx eax, byte [rsi + OP_BASE]
    cmp eax, NONE
    je .rex
    shr eax, 3
    or r10d, eax                ; B
.rex:
    test r10d, r10d
    jz .opcode
    lea eax, [r10 + 0x40]
    call emit8
.opcode:
    pop rax
    call emit8
    and r9d, 7
    shl r9d, 3                  ; reg, in place
    cmp byte [rsi + OP_KIND], K_REG
    jne .memory
    movzx eax, byte [rsi + OP_REG]
    and eax, 7
    or eax, r9d
    or eax, 0xC0
    jmp emit8
.memory:
    cmp byte [rsi + OP_RIP], 0
    je .not_rip
    lea eax, [r9 + 5]           ; mod 0, r/m 5: [rip + disp32]
    call emit8
    mov [rel rip_at], r15
    mov rax, [rsi + OP_VALUE]
    mov [rel rip_to], rax
    xor eax, eax
    jmp emit32
.not_rip:
    mov r8, [rsi + OP_VALUE]    ; the displacement
    movzx r10d, byte [rsi + OP_BASE]
    movzx r11d, byte [rsi + OP_INDEX]
    cmp r10d, NONE
    jne .based
    lea eax, [r9 + 4]           ; no base: SIB with base 5, mod 0, disp32
    call emit8
    call sib_scale_index
    or eax, 5
    call emit8
    mov eax, r8d
    jmp emit32
.based:
    xor ecx, ecx                ; mod
    test r8, r8
    jnz .disp_size
    mov eax, r10d
    and eax, 7
    cmp eax, 5                  ; rbp / r13 can't have mod 0
    jne .have_mod
.disp_size:
    mov ecx, 1
    movsx rax, r8b
    cmp rax, r8
    je .have_mod
    mov ecx, 2
.have_mod:
    mov eax, ecx
    shl eax, 6
    or eax, r9d
    mov edx, r10d
    and edx, 7
    cmp r11d, NONE
    jne .sib
    cmp edx, 4                  ; rsp / r12 need a SIB
    je .sib
    or eax, edx
    call emit8
    jmp .disp
.sib:
    or eax, 4
    call emit8
    call sib_scale_index
    or eax, edx
    call emit8
.disp:
    cmp ecx, 1
    jb .done
    mov eax, r8d
    ja .disp32
    jmp emit8
.disp32:
    jmp emit32
.done:
    ret

sib_scale_index:                ; eax = scale << 6 | index << 3 (4: no index)
    movzx eax, byte [rsi + OP_SCALE]
    shl eax, 6
    cmp r11d, NONE
    jne .index
    or eax, 4 << 3
    ret
.index:
    push rdx
    mov edx, r11d
    and edx, 7
    shl edx, 3
    or eax, edx
    pop rdx
    ret

finish:                         ; patch a rip-relative displacement: target − end
    mov rax, [rel rip_at]
    test rax, rax
    jz .done
    mov rdx, [rel rip_to]
    sub rdx, r15
    lea rcx, [rel out]
    mov [rcx + rax], edx
.done:
    ret

emit8:                          ; (they keep every register but r15)
    push rcx
    lea rcx, [rel out]
    mov [rcx + r15], al
    inc r15
    pop rcx
    ret
emit32:
    push rcx
    lea rcx, [rel out]
    mov [rcx + r15], eax
    add r15, 4
    pop rcx
    ret
emit64:
    push rcx
    lea rcx, [rel out]
    mov [rcx + r15], rax
    add r15, 8
    pop rcx
    ret

; ---- parsing ------------------------------------------------------------------------

skip_spaces:
    cmp r12, r13
    jae .done
    cmp byte [r12], ' '
    je .skip
    cmp byte [r12], 9
    jne .done
.skip:
    inc r12
    jmp skip_spaces
.done:
    ret

read_word:                      ; letters, digits, _ and . into `name`, NUL-padded
    lea rdi, [rel name]
    xor eax, eax
    mov [rdi], rax
    mov [rdi + 8], rax
    mov [rdi + 16], rax
    mov [rdi + 24], rax
    xor ecx, ecx
.char:
    cmp r12, r13
    jae .done
    movzx eax, byte [r12]
    cmp al, '_'
    je .take
    cmp al, '.'
    je .take
    cmp al, '0'
    jb .done
    cmp al, '9'
    jbe .take
    or al, 0x20
    cmp al, 'a'
    jb .done
    cmp al, 'z'
    ja .done
    mov al, [r12]
.take:
    cmp ecx, 23
    jae .skip
    mov [rdi + rcx], al
    inc ecx
.skip:
    inc r12
    jmp .char
.done:
    ret

operand:                        ; parse one operand into the record at rdi
    push rbx
    mov rbx, rdi
    mov byte [rbx + OP_SIZE], 0
    mov byte [rbx + OP_RIP], 0
    mov word [rbx + OP_BASE], NONE | NONE << 8
    mov byte [rbx + OP_SCALE], 0
    mov qword [rbx + OP_VALUE], 0
    call skip_spaces
    lea rsi, [rel qword_kw]
    call keyword
    jne .not_qword
    mov byte [rbx + OP_SIZE], 8
.not_qword:
    lea rsi, [rel dword_kw]
    call keyword
    jne .not_dword
    mov byte [rbx + OP_SIZE], 4
.not_dword:
    cmp byte [r12], '['
    je .memory
    cmp byte [r12], '-'
    je .number
    cmp byte [r12], '0'
    jb .name
    cmp byte [r12], '9'
    jbe .number
.name:
    call read_word
    call register
    jc .label
    mov byte [rbx + OP_KIND], K_REG
    mov [rbx + OP_REG], al
    mov [rbx + OP_WIDE], dl
    jmp .done
.label:
    call label_value
    mov [rbx + OP_VALUE], rax
    mov byte [rbx + OP_KIND], K_IMM
    jmp .done
.number:
    call number
    mov [rbx + OP_VALUE], rax
    mov byte [rbx + OP_KIND], K_IMM
    jmp .done
.memory:
    mov byte [rbx + OP_KIND], K_MEM
    inc r12                     ; [
    cmp byte [r12], 'r'
    jne .term
    cmp dword [r12], 'rel '
    jne .term
    add r12, 4
    mov byte [rbx + OP_RIP], 1
    cmp byte [r12], '0'
    jb .rel_label
    cmp byte [r12], '9'
    ja .rel_label
    call number
    jmp .rel_value
.rel_label:
    call read_word
    call label_value
.rel_value:
    mov [rbx + OP_VALUE], rax
    jmp .close
.term:                          ; terms joined by + and -
    mov r8d, 1                  ; the sign
.term_sign:
    cmp byte [r12], '+'
    jne .not_plus
    inc r12
    jmp .term_sign
.not_plus:
    cmp byte [r12], '-'
    jne .term_value
    neg r8d
    inc r12
    jmp .term_sign
.term_value:
    cmp byte [r12], '0'
    jb .term_reg
    cmp byte [r12], '9'
    ja .term_reg
    call number
    cmp r8d, 1
    je .add_disp
    neg rax
.add_disp:
    add [rbx + OP_VALUE], rax
    jmp .next_term
.term_reg:
    call read_word
    call register
    cmp byte [r12], '*'
    jne .base_or_index
    inc r12
    movzx ecx, byte [r12]       ; the scale: 1, 2, 4, 8
    inc r12
    sub ecx, '0'
    bsf ecx, ecx
    mov [rbx + OP_SCALE], cl
    mov [rbx + OP_INDEX], al
    jmp .next_term
.base_or_index:
    cmp byte [rbx + OP_BASE], NONE
    jne .as_index
    mov [rbx + OP_BASE], al
    jmp .next_term
.as_index:
    mov [rbx + OP_INDEX], al
.next_term:
    cmp byte [r12], ']'
    jne .term
.close:
    inc r12                     ; ]
.done:
    pop rbx
    ret

keyword:                        ; ZF = 1 (and skipped) if the 6 bytes at rsi are at r12
    mov rax, r13
    sub rax, r12
    cmp rax, 6
    jb .no
    mov eax, [rsi]
    cmp eax, [r12]
    jne .no
    mov ax, [rsi + 4]
    cmp ax, [r12 + 4]
    jne .no
    add r12, 6
    cmp eax, eax                ; ZF = 1
    ret
.no:
    test esp, esp               ; ZF = 0
    ret

register:                       ; `name` -> al = number, dl = 64-bit; CF = 1 if not one
    lea rsi, [rel registers]
    mov rcx, [rel name]
.next:
    mov rdx, [rsi]
    test rdx, rdx
    jz .no
    cmp rdx, rcx
    je .yes
    add rsi, 10
    jmp .next
.yes:
    mov al, [rsi + 8]
    mov dl, [rsi + 9]
    clc
    ret
.no:
    stc
    ret

label_value:                    ; `name` -> rax = its address (0 if unknown: pass 1)
    lea rsi, [rel labels]
    mov rcx, [rel nlabels]
.next:
    test rcx, rcx
    jz .unknown
    mov rax, [rsi]
    cmp rax, [rel name]
    jne .skip
    mov rax, [rsi + 8]
    cmp rax, [rel name + 8]
    jne .skip
    mov rax, [rsi + 16]
    cmp rax, [rel name + 16]
    jne .skip
    mov rax, [rsi + 24]
    ret
.skip:
    add rsi, 32
    dec rcx
    jmp .next
.unknown:
    xor eax, eax
    ret

number:                         ; [-]0x... or [-]decimal at r12 -> rax
    xor eax, eax
    xor r9d, r9d                ; negative?
    cmp byte [r12], '-'
    jne .unsigned
    inc r9d
    inc r12
.unsigned:
    cmp byte [r12], '0'
    jne .decimal
    mov cl, [r12 + 1]
    or cl, 0x20
    cmp cl, 'x'
    jne .decimal
    add r12, 2
.hex:
    movzx ecx, byte [r12]
    sub ecx, '0'
    cmp ecx, 9
    jbe .hex_digit
    movzx ecx, byte [r12]
    or ecx, 0x20
    sub ecx, 'a'
    cmp ecx, 5
    ja .sign
    add ecx, 10
.hex_digit:
    shl rax, 4
    or rax, rcx
    inc r12
    jmp .hex
.decimal:
    movzx ecx, byte [r12]
    sub ecx, '0'
    cmp ecx, 9
    ja .sign
    imul rax, rax, 10
    add rax, rcx
    inc r12
    jmp .decimal
.sign:
    test r9d, r9d
    jz .done
    neg rax
.done:
    ret
