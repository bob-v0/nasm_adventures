; Level 169 — The Flags Register
;
; Part 2: when your code finishes, flags must be CF=1 ZF=1 SF=0 OF=1.
; (Your code goes here. You can also paste operations here to test your
;  predictions in the debugger, as long as the LAST one leaves the right flags.)


section .data
; Part 1: your predictions. Four bytes per operation: CF, ZF, SF, OF (0 or 1).
answers:
    db 0, 0, 0, 0       ; 1. mov al, 0xFF  / add al, 1
    db 0, 0, 0, 0       ; 2. mov al, 0x7F  / add al, 1
    db 0, 0, 0, 0       ; 3. mov al, 0x80  / sub al, 1
    db 0, 0, 0, 0       ; 4. mov al, 0     / sub al, 1
    db 0, 0, 0, 0       ; 5. mov eax, 5    / sub eax, 5
    db 0, 0, 0, 0       ; 6. mov rax, -1   / add rax, -1
    db 0, 0, 0, 0       ; 7. mov al, 0x80  / add al, 0x80
    db 0, 0, 0, 0       ; 8. mov al, 0x40  / add al, 0x40
