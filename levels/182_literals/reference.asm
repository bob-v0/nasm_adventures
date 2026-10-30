mov rax, 0b10101010_10101010_10101010_10101010_10101010_10101010_10101010_10101010
mov rbx, 'NASM'           ; = 0x4D53414E: 'N' is the lowest byte
mov rcx, -1
mov rdx, 0o755
mov rsi, 1_000_000_000_000
mov rdi, 0BEEFh           ; leading 0 so NASM doesn't read BEEFh as a label
