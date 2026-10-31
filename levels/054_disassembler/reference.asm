; Level 54 — Disassembler (reference)
;
; Reads machine code from stdin, prints one instruction per line. Decoding fills the
; m_* variables (the r/m operand); printing happens once the whole instruction has been
; read, because a rip-relative address needs the address of the NEXT instruction.

global _start

section .rodata
alu0: db "add", 0
alu1: db "or", 0
alu2: db "adc", 0
alu3: db "sbb", 0
alu4: db "and", 0
alu5: db "sub", 0
alu6: db "xor", 0
alu7: db "cmp", 0
alu: dq alu0, alu1, alu2, alu3, alu4, alu5, alu6, alu7
cc0: db "jo", 0
cc1: db "jno", 0
cc2: db "jb", 0
cc3: db "jae", 0
cc4: db "je", 0
cc5: db "jne", 0
cc6: db "jbe", 0
cc7: db "ja", 0
cc8: db "js", 0
cc9: db "jns", 0
cc10: db "jp", 0
cc11: db "jnp", 0
cc12: db "jl", 0
cc13: db "jge", 0
cc14: db "jle", 0
cc15: db "jg", 0
cc: dq cc0, cc1, cc2, cc3, cc4, cc5, cc6, cc7, cc8, cc9, cc10, cc11, cc12, cc13, cc14, cc15
r64: db "rax", 0, "rcx", 0, "rdx", 0, "rbx", 0, "rsp", 0, "rbp", 0, "rsi", 0, "rdi", 0
     db "r8", 0, 0, "r9", 0, 0, "r10", 0, "r11", 0, "r12", 0, "r13", 0, "r14", 0, "r15", 0
r32: db "eax", 0, "ecx", 0, "edx", 0, "ebx", 0, "esp", 0, "ebp", 0, "esi", 0, "edi", 0
     db "r8d", 0, "r9d", 0
     db "r10d", "r11d", "r12d", "r13d", "r14d", "r15d"     ; (4 chars each, no NUL)
s_mov: db "mov", 0
s_test: db "test", 0
s_lea: db "lea", 0
s_inc: db "inc", 0
s_dec: db "dec", 0
s_push: db "push", 0
s_pop: db "pop", 0
s_jmp: db "jmp", 0
s_call: db "call", 0
s_ret: db "ret", 0
s_nop: db "nop", 0
s_syscall: db "syscall", 0
s_qword: db "qword ", 0
s_dword: db "dword ", 0
s_rel: db "rel ", 0
s_bad: db "(bad)", 0
hexdigits: db "0123456789abcdef"

section .bss
buf:    resb 65536
out:    resb 1 << 20
m_mem:  resb 1          ; the r/m operand is memory
m_rip:  resb 1
m_base: resd 1          ; −1: none
m_index: resd 1         ; −1: none
m_scale: resd 1
m_rm:   resd 1          ; register number when not memory
m_reg:  resd 1          ; ModRM.reg with REX.R
m_disp: resq 1
wide:   resb 1          ; REX.W

section .text
_start:
    xor r13d, r13d              ; bytes read
.read:
    xor eax, eax
    xor edi, edi
    lea rsi, [rel buf]
    add rsi, r13
    mov edx, 65536
    sub edx, r13d
    jz .read_done
    syscall
    test rax, rax
    jle .read_done
    add r13, rax
    jmp .read
.read_done:
    lea r12, [rel buf]
    lea r15, [rel out]
    xor r14d, r14d              ; the instruction's offset
.insn:
    cmp r14, r13
    jae .finish
    mov rbx, r14
    xor ebp, ebp                ; REX
    call fetch8
    mov ecx, eax
    and ecx, 0xF0
    cmp ecx, 0x40
    jne .no_rex
    mov ebp, eax
    call fetch8
.no_rex:
    mov ecx, ebp
    shr ecx, 3
    and ecx, 1
    mov [rel wide], cl
    cmp al, 0x0F
    je .two_byte
    cmp al, 0xC3
    je .ret
    cmp al, 0x90
    je .nop
    cmp al, 0xEB
    je .jmp8
    cmp al, 0xE8
    je .call32
    cmp al, 0xE9
    je .jmp32
    mov ecx, eax
    and ecx, 0xF0
    cmp ecx, 0x70
    je .jcc8
    cmp ecx, 0x50
    je .pushpop
    mov ecx, eax
    and ecx, 0xF8
    cmp ecx, 0xB8
    je .movimm_reg
    cmp al, 0x81
    je .group1_32
    cmp al, 0x83
    je .group1_8
    cmp al, 0xC7
    je .mov_imm
    cmp al, 0xFF
    je .incdec
    cmp al, 0x89
    je .mov_to_rm
    cmp al, 0x8B
    je .mov_to_reg
    cmp al, 0x85
    je .test
    cmp al, 0x8D
    je .lea
    cmp al, 0x40
    jae .bad
    mov ecx, eax                ; 01/03/09/0B/.../3B: alu
    and ecx, 7
    cmp ecx, 1
    je .alu_to_rm
    cmp ecx, 3
    je .alu_to_reg
.bad:
    lea rsi, [rel s_bad]
    call emit_str
    mov r14, r13                ; give up on the rest
    jmp .eol

.alu_to_rm:
    shr eax, 3
    lea rsi, [rel alu]
    mov rsi, [rsi + rax*8]
    jmp .rm_reg
.alu_to_reg:
    shr eax, 3
    lea rsi, [rel alu]
    mov rsi, [rsi + rax*8]
    jmp .reg_rm
.mov_to_rm:
    lea rsi, [rel s_mov]
    jmp .rm_reg
.mov_to_reg:
    lea rsi, [rel s_mov]
    jmp .reg_rm
.test:
    lea rsi, [rel s_test]
    jmp .rm_reg
.lea:
    lea rsi, [rel s_lea]
    jmp .reg_rm

.rm_reg:                        ; name r/m, reg
    push rsi
    call parse_modrm
    pop rsi
    call emit_name
    xor ecx, ecx                ; no size keyword: the register says it
    call emit_rm
    call emit_comma
    mov eax, [rel m_reg]
    call emit_reg
    jmp .next
.reg_rm:                        ; name reg, r/m
    push rsi
    call parse_modrm
    pop rsi
    call emit_name
    mov eax, [rel m_reg]
    call emit_reg
    call emit_comma
    xor ecx, ecx
    call emit_rm
    jmp .next

.group1_8:
    call parse_modrm
    call fetch8
    movsx rax, al
    jmp .group1
.group1_32:
    call parse_modrm
    call fetch32
.group1:
    push rax
    mov eax, [rel m_reg]
    and eax, 7
    lea rsi, [rel alu]
    mov rsi, [rsi + rax*8]
    jmp .rm_imm
.mov_imm:
    call parse_modrm
    call fetch32
    push rax
    lea rsi, [rel s_mov]
.rm_imm:                        ; name [size] r/m, signed imm (on the stack)
    call emit_name
    mov ecx, 1
    call emit_rm
    call emit_comma
    pop rax
    call emit_shex
    jmp .next
.incdec:
    call parse_modrm
    mov eax, [rel m_reg]
    and eax, 7
    lea rsi, [rel s_inc]
    cmp eax, 1
    jb .incdec_name
    lea rsi, [rel s_dec]
    ja .bad
.incdec_name:
    call emit_name
    mov ecx, 1
    call emit_rm
    jmp .next

.movimm_reg:                    ; B8+r: mov r, imm32 / imm64 (unsigned)
    and eax, 7
    mov ecx, ebp
    and ecx, 1                  ; REX.B
    shl ecx, 3
    or eax, ecx
    push rax
    lea rsi, [rel s_mov]
    call emit_name
    pop rax
    call emit_reg
    call emit_comma
    cmp byte [rel wide], 0
    jne .imm64
    call fetch32
    mov eax, eax
    jmp .imm_out
.imm64:
    mov rax, [r12 + rbx]
    add rbx, 8
.imm_out:
    call emit_hex
    jmp .next

.pushpop:
    mov ecx, eax
    and eax, 7
    mov edx, ebp
    and edx, 1
    shl edx, 3
    or eax, edx
    push rax
    lea rsi, [rel s_push]
    test ecx, 8
    jz .pp_name
    lea rsi, [rel s_pop]
.pp_name:
    call emit_name
    pop rax
    mov byte [rel wide], 1      ; always 64-bit
    call emit_reg
    jmp .next

.jcc8:
    and eax, 15
    lea rsi, [rel cc]
    mov rsi, [rsi + rax*8]
    jmp .rel8
.jmp8:
    lea rsi, [rel s_jmp]
.rel8:
    push rsi
    call fetch8
    movsx rax, al
    jmp .branch
.call32:
    lea rsi, [rel s_call]
    jmp .rel32
.jmp32:
    lea rsi, [rel s_jmp]
.rel32:
    push rsi
    call fetch32
.branch:                        ; target = the next instruction + rel
    add rax, rbx
    pop rsi
    push rax
    call emit_name
    pop rax
    call emit_shex
    jmp .next

.two_byte:
    call fetch8
    cmp al, 0x05
    je .syscall
    mov ecx, eax
    and ecx, 0xF0
    cmp ecx, 0x80
    jne .bad
    and eax, 15
    lea rsi, [rel cc]
    mov rsi, [rsi + rax*8]
    jmp .rel32
.syscall:
    lea rsi, [rel s_syscall]
    jmp .alone
.ret:
    lea rsi, [rel s_ret]
    jmp .alone
.nop:
    lea rsi, [rel s_nop]
.alone:
    call emit_str
.next:
    mov r14, rbx
.eol:
    mov byte [r15], 10
    inc r15
    jmp .insn

.finish:
    mov eax, 1
    mov edi, 1
    lea rsi, [rel out]
    mov rdx, r15
    sub rdx, rsi
    syscall
    mov eax, 60
    xor edi, edi
    syscall

; ---- decoding ---------------------------------------------------------------------

fetch8:                         ; al = the next byte (movzx into eax)
    movzx eax, byte [r12 + rbx]
    inc rbx
    ret

fetch32:                        ; rax = the next 4 bytes, sign-extended
    movsxd rax, dword [r12 + rbx]
    add rbx, 4
    ret

parse_modrm:                    ; ebp = REX; fills m_*
    call fetch8
    mov ecx, eax
    shr ecx, 3
    and ecx, 7
    mov edx, ebp
    and edx, 4                  ; REX.R
    shl edx, 1
    or ecx, edx
    mov [rel m_reg], ecx
    mov ecx, eax
    shr ecx, 6                  ; mod
    and eax, 7                  ; r/m
    mov edx, ebp
    and edx, 1                  ; REX.B
    shl edx, 3
    mov byte [rel m_rip], 0
    mov qword [rel m_disp], 0
    mov dword [rel m_index], -1
    mov dword [rel m_scale], 0
    cmp ecx, 3
    jne .memory
    or eax, edx
    mov [rel m_rm], eax
    mov byte [rel m_mem], 0
    ret
.memory:
    mov byte [rel m_mem], 1
    cmp eax, 4
    je .sib
    cmp eax, 5
    jne .base
    test ecx, ecx
    jnz .base
    mov byte [rel m_rip], 1     ; mod 0, r/m 5: [rip + disp32]
    call fetch32
    mov [rel m_disp], rax
    ret
.base:
    or eax, edx
    mov [rel m_base], eax
    jmp .displacement
.sib:
    push rcx
    call fetch8
    pop rcx
    mov esi, eax
    shr esi, 6
    mov [rel m_scale], esi
    mov esi, eax
    shr esi, 3
    and esi, 7
    mov edi, ebp
    and edi, 2                  ; REX.X
    shl edi, 2
    or esi, edi
    cmp esi, 4
    je .no_index
    mov [rel m_index], esi
.no_index:
    and eax, 7
    cmp eax, 5
    jne .sib_base
    test ecx, ecx
    jnz .sib_base
    mov dword [rel m_base], -1  ; mod 0, base 5: no base, disp32
    call fetch32
    mov [rel m_disp], rax
    ret
.sib_base:
    or eax, edx
    mov [rel m_base], eax
.displacement:
    cmp ecx, 1
    jne .disp32
    call fetch8
    movsx rax, al
    mov [rel m_disp], rax
    ret
.disp32:
    cmp ecx, 2
    jne .done
    call fetch32
    mov [rel m_disp], rax
.done:
    ret

; ---- printing ----------------------------------------------------------------------

emit_str:                       ; rsi = a NUL-terminated string
    mov al, [rsi]
    test al, al
    jz .done
    mov [r15], al
    inc r15
    inc rsi
    jmp emit_str
.done:
    ret

emit_name:                      ; the mnemonic and a space
    call emit_str
    mov byte [r15], ' '
    inc r15
    ret

emit_comma:
    mov word [r15], ', '
    add r15, 2
    ret

emit_reg:                       ; eax = register number; wide = 64-bit
    lea rsi, [rel r64]
    cmp byte [rel wide], 0
    jne .table
    lea rsi, [rel r32]
.table:
    mov ecx, [rsi + rax*4]      ; up to 4 characters
.char:
    test cl, cl
    jz .done
    mov [r15], cl
    inc r15
    shr ecx, 8
    jnz .char
.done:
    ret

emit_reg64:                     ; eax = register number, always 64-bit
    mov cl, [rel wide]
    push rcx
    mov byte [rel wide], 1
    call emit_reg
    pop rcx
    mov [rel wide], cl
    ret

emit_rm:                        ; ecx = 1: a size keyword for memory
    cmp byte [rel m_mem], 0
    jne .memory
    mov eax, [rel m_rm]
    jmp emit_reg
.memory:
    test ecx, ecx
    jz .open
    lea rsi, [rel s_qword]
    cmp byte [rel wide], 0
    jne .size
    lea rsi, [rel s_dword]
.size:
    call emit_str
.open:
    mov byte [r15], '['
    inc r15
    cmp byte [rel m_rip], 0
    je .parts
    lea rsi, [rel s_rel]
    call emit_str
    mov rax, [rel m_disp]
    add rax, rbx                ; relative to the next instruction
    call emit_shex
    jmp .close
.parts:
    xor edx, edx                ; something printed yet?
    mov eax, [rel m_base]
    cmp eax, -1
    je .index
    call emit_reg64
    mov edx, 1
.index:
    mov eax, [rel m_index]
    cmp eax, -1
    je .disp
    test edx, edx
    jz .no_plus
    mov byte [r15], '+'
    inc r15
.no_plus:
    call emit_reg64
    mov edx, 1
    mov ecx, [rel m_scale]
    test ecx, ecx
    jz .disp
    mov byte [r15], '*'
    mov eax, 1
    shl eax, cl
    add al, '0'
    mov [r15 + 1], al
    add r15, 2
.disp:
    mov rax, [rel m_disp]
    test edx, edx
    jnz .offset
    call emit_shex              ; nothing else: the displacement alone
    jmp .close
.offset:
    test rax, rax
    jz .close
    jns .plus
    mov byte [r15], '-'
    inc r15
    neg rax
    call emit_hex
    jmp .close
.plus:
    mov byte [r15], '+'
    inc r15
    call emit_hex
.close:
    mov byte [r15], ']'
    inc r15
    ret

emit_shex:                      ; rax signed
    test rax, rax
    jns emit_hex
    mov byte [r15], '-'
    inc r15
    neg rax
emit_hex:                       ; rax unsigned: 0x and the digits, no leading zeros
    mov word [r15], '0x'
    add r15, 2
    lea rsi, [rel hexdigits]
    mov ecx, 60
.skip:
    mov rdx, rax
    shr rdx, cl
    test edx, 15
    jnz .digit
    sub ecx, 4
    jns .skip
    mov byte [r15], '0'         ; the value 0
    inc r15
    ret
.digit:
    mov rdx, rax
    shr rdx, cl
    and edx, 15
    mov dl, [rsi + rdx]
    mov [r15], dl
    inc r15
    sub ecx, 4
    jns .digit
    ret
