; Level 80 — Condition Variables
;
; A bounded blocking queue for threads:
;   queue_init(q, cap)     q: 4096 zeroed bytes for your struct; cap: 1..64
;   queue_put(q, value)    sleeps while the queue is full
;   queue_get(q)           sleeps while it's empty -> rax = value, rdx = 1
;                          once closed and empty    -> rdx = 0
;   queue_close(q)         no more puts; wakes every sleeping getter
; The harness gives you mutex_lock / mutex_unlock (level 87's). Waiting threads must
; sleep (futex), not spin.

global queue_init, queue_put, queue_get, queue_close
extern mutex_lock, mutex_unlock

section .text
queue_init:
    ret

queue_put:
    ret

queue_get:
    xor edx, edx
    ret

queue_close:
    ret
