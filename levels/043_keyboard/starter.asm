; Level 43 — Keyboard
;
; A line editor, talking to the keyboard controller directly (no int 0x16):
;   1. send "> " to the serial port (COM1): the game starts typing when it sees it;
;   2. read keys from the PS/2 controller (ports 0x60, 0x64) and build a line:
;      letters, digits and space are added (with Shift: capital letters), Backspace
;      removes the last character (if any), at most 70 characters (more are ignored);
;      show the line on the screen as it changes;
;   3. on Enter, send the line and CR LF to COM1, and halt.

bits 16
org 0x7C00

start:
    ; TODO
    cli
    hlt

times 510 - ($ - $$) db 0
dw 0xAA55
