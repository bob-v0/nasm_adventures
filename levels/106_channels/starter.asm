; Level 106 — Channels
;
; A bounded channel between tasks (the game's task runtime, rt_*, is linked in):
;
;   chan_init(ch, cap)        ch: 4096 zeroed bytes for your struct; cap: 1..64
;   chan_send(ch, value)      waits while the channel is full
;   chan_recv(ch)             waits while it's empty -> rax = value, rdx = 1
;                             once closed and empty   -> rdx = 0
;   chan_close(ch)            no more sends; waiting receivers must wake up
;
; Waiting means parking the task (rt_park) after leaving a waker (rt_current) where the
; other side will find it and rt_unpark it, not spinning with rt_yield.

global chan_init, chan_send, chan_recv, chan_close
extern rt_park, rt_unpark, rt_current, rt_yield

section .text
chan_init:
    ret

chan_send:
    xor eax, eax
    ret

chan_recv:
    xor edx, edx
    ret

chan_close:
    ret
