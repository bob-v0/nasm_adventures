; Level 87 — Locks
;
; mutex_lock(m) / mutex_unlock(m): m points to a zeroed dword. One thread at a time may
; hold the lock.
; This is a spinlock: correct, and a waiting thread burns its whole turn spinning while
; the holder can't even run. Make waiting threads SLEEP (futex) instead, and make
; unlocking cheap when nobody waits.

global mutex_lock, mutex_unlock

section .text
mutex_lock:                     ; rdi = the lock
    mov eax, 1
    xchg eax, [rdi]             ; take it, and see whether it was free
    test eax, eax
    jz .got
.spin:
    pause                       ; (a hint to the CPU: we're spinning)
    cmp dword [rdi], 0
    jne .spin
    jmp mutex_lock
.got:
    ret

mutex_unlock:                   ; rdi = the lock
    mov dword [rdi], 0
    ret
