; Level 46 — Port I/O
;
; Without the BIOS (no int), send this line out of the first serial port, COM1:
;     Hello, serial port! Today is YYYY-MM-DD.<CR><LF>
; with today's date from the CMOS real-time clock. Then halt.
;
; COM1 is a 16550 UART at ports 0x3F8-0x3FF; the CMOS clock is behind ports 0x70/0x71.

bits 16
org 0x7C00

start:
    ; TODO
    cli
    hlt

times 510 - ($ - $$) db 0
dw 0xAA55
