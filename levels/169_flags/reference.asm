mov al, 0x80
add al, 0x80        ; 0x100 -> 0x00: carry out, zero, and -128 + -128 overflows

section .data
answers:            ;  CF ZF SF OF
    db 1, 1, 0, 0   ; 1. 0xFF + 1    = 0x00
    db 0, 0, 1, 1   ; 2. 0x7F + 1    = 0x80  (127 + 1 overflows to -128)
    db 0, 0, 0, 1   ; 3. 0x80 - 1    = 0x7F  (-128 - 1 overflows to 127)
    db 1, 0, 1, 0   ; 4. 0 - 1       = 0xFF  (borrow)
    db 0, 1, 0, 0   ; 5. 5 - 5       = 0
    db 1, 0, 1, 0   ; 6. -1 + -1     = -2    (unsigned: carry; signed: fine)
    db 1, 1, 0, 1   ; 7. 0x80 + 0x80 = 0x00
    db 0, 0, 1, 1   ; 8. 0x40 + 0x40 = 0x80  (64 + 64 overflows to -128)
