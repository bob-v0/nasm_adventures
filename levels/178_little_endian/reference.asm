movzx eax, word [packet]       ; bytes CA FE load as 0xFECA ...
xchg al, ah                    ; ... so swap them: 0xCAFE
movzx ebx, word [packet + 2]
xchg bl, bh
mov ecx, [packet + 4]
bswap ecx                      ; 32-bit write: upper half of rcx is 0
mov rdx, [packet + 8]
bswap rdx
mov [seq_out], ecx             ; stored little-endian again
mov r8, [packet]               ; the "wrong" view
