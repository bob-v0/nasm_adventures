; Level 83 — Memory Ordering
;
; The "store buffer" litmus test. x, y, r1, r2 are dwords, all 0 at the start.
;     left:  x = 1;  r1 = y          right:  y = 1;  r2 = x
; The game's harness runs left and right in two threads at the same time.
;
; 1. sb_left / sb_right: exactly the above, nothing more. Then find a schedule in which
;    BOTH r1 and r2 end up 0 (which no interleaving of the four steps could produce)
;    and write it down:   ;! witness schedule = N
; 2. fenced_left / fenced_right: the same, but such that r1 = r2 = 0 can never happen.

global sb_left, sb_right, fenced_left, fenced_right
extern x, y, r1, r2

section .text
sb_left:
    ; TODO
    ret

sb_right:
    ; TODO
    ret

fenced_left:
    ; TODO
    ret

fenced_right:
    ; TODO
    ret
