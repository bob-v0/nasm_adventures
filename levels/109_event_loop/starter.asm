; Level 109 — Event Loop
;
; An echo server on 127.0.0.1:7000 for any number of clients at once, in ONE thread:
;   socket, bind, listen; then an epoll loop:
;     the listening socket is ready -> accept the new client, watch it too
;     a client is ready             -> read what it sent, write it straight back;
;                                      read returns 0: it's gone, close it
; Never exit (the game stops you when every client is done).

global _start

section .text
_start:
    ; TODO
    mov eax, 60
    xor edi, edi
    syscall

section .data
addr: dw 2                      ; struct sockaddr_in: AF_INET
      db 7000 >> 8, 7000 & 0xFF ; the port, big-endian (network byte order)
      db 127, 0, 0, 1           ; the address 127.0.0.1
      times 8 db 0
