lea rcx, [rdi + rdi*4]          ; x * 5
lea rcx, [rcx + rcx*8]          ; x * 45
mov r8, rdi
shr r8, 3                       ; x / 8
mov r9, rdi
shl r9, 10                      ; x * 1024
mov rax, 0xCCCCCCCCCCCCCCCD     ; ceil(2^67 / 10)
mul rdi                         ; rdx = (x * m) >> 64
shr rdx, 3                      ; quotient = (x * m) >> 67
mov rax, rdx
lea rdx, [rax + rax*4]          ; 5q
mov rbx, rdi                    ; x
sub rbx, rdx
sub rbx, rdx                    ; x - 10q
