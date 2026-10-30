; Shared by the game's tiny /bin utilities (installed in the emulated filesystem).
%macro EXIT 1
    mov eax, 60
    mov edi, %1
    syscall
%endmacro

%macro WRITE 3                  ; fd, buffer, length
    mov rdx, %3
    mov rsi, %2
    mov edi, %1
    mov eax, 1
    syscall
%endmacro
