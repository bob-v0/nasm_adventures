; Level 113 — ELF by Hand
;
; Assembled with `nasm -f bin`: no linker. Every byte of the output file comes from
; this source, including the headers the kernel reads before running anything.
; The program must write "hand-made\n" and exit with 42. The file must be at most
; 256 bytes.
bits 64
org 0x400000                    ; the address byte 0 of the file will be loaded at

ehdr:                           ; ELF64 header: 64 bytes
    db 0x7F, "ELF"              ; magic
    ; TODO: EI_CLASS, EI_DATA, EI_VERSION, EI_OSABI, then 8 bytes of padding
    ; TODO: e_type (2 bytes), e_machine (2), e_version (4)
    ; TODO: e_entry (8), e_phoff (8), e_shoff (8), e_flags (4)
    ; TODO: e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx (2 each)

phdr:                           ; a program header: 56 bytes
    ; TODO

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
