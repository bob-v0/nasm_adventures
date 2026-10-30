; Provided by level 150: the program to run (64 bytes) and the VM's stack (32 qwords).
section .data
code:   times 64 db 0
vstack: times 32 dq 0
