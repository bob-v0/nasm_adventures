; Level 44 — Real-Mode Interrupts
;
; Install a handler for int 0x80 with three services, then load the game's test program
; (2 sectors from LBA 1, as in level 45) at 0000:8000 and jump to 0000:8004. It calls
; your services and reports on the serial port.
;
;   ah = 0: send the character al to COM1
;   ah = 1: ax = bx + cx
;   ah = 2: send the NUL-terminated string at ds:si to COM1; cx = its length
;   any other ah: do nothing but return with the carry flag set
; After a service that worked the carry flag is clear. Every register that isn't a
; result (and every segment register) is as the caller left it.

bits 16
org 0x7C00

start:
    ; TODO
    cli
    hlt

times 510 - ($ - $$) db 0
dw 0xAA55
