; Level 113 — ELF by Hand (reference)
; nasm -f bin: every byte of the file is written here.
bits 64
org 0x400000                    ; where the file will be mapped (vaddr of byte 0)

ehdr:                           ; ELF64 header (64 bytes)
    db 0x7F, "ELF"              ; magic
    db 2                        ; EI_CLASS: 64-bit
    db 1                        ; EI_DATA: little-endian
    db 1                        ; EI_VERSION
    db 0                        ; EI_OSABI: System V
    times 8 db 0                ; padding
    dw 2                        ; e_type: ET_EXEC
    dw 0x3E                     ; e_machine: x86-64
    dd 1                        ; e_version
    dq _start                   ; e_entry
    dq phdr - $$                ; e_phoff
    dq 0                        ; e_shoff: no section headers
    dd 0                        ; e_flags
    dw EHDR_SIZE                ; e_ehsize
    dw PHDR_SIZE                ; e_phentsize
    dw 1                        ; e_phnum
    dw 0, 0, 0                  ; e_shentsize, e_shnum, e_shstrndx
EHDR_SIZE equ $ - ehdr

phdr:                           ; one program header: map the whole file
    dd 1                        ; p_type: PT_LOAD
    dd 5                        ; p_flags: R + X
    dq 0                        ; p_offset
    dq $$                       ; p_vaddr
    dq $$                       ; p_paddr
    dq FILE_SIZE                ; p_filesz
    dq FILE_SIZE                ; p_memsz
    dq 0x1000                   ; p_align
PHDR_SIZE equ $ - phdr

_start:
    mov eax, 1                  ; write(1, msg, MSG_LEN)
    mov edi, eax
    lea rsi, [rel msg]
    mov edx, MSG_LEN
    syscall
    mov eax, 60                 ; exit(42)
    mov edi, 42
    syscall

msg: db "hand-made", 10
MSG_LEN equ $ - msg

FILE_SIZE equ $ - $$
