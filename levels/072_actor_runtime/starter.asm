; Level 72 — Lock-Free Actor Runtime (boss)
;
; The whole runtime, yours:
;   rt_init(workers)               start that many worker threads (at most 8)
;   actor_new(behavior) -> actor   a new actor on the heap (the game's allocator:
;                                  syscall 0x1000 = malloc(rdi), 0x1001 = free(rdi));
;                                  the caller holds one reference
;   actor_send(actor, msg)         from any thread, including from inside a behavior
;   actor_release(actor)           drop a reference; the last one frees the actor
;   rt_shutdown()                  wait until every message sent has been handled,
;                                  then stop the workers and wait for them
; Workers run actors: an actor's behavior(actor, msg) is called for each of its messages,
; never on two workers at once. msg: dq next, dq value; the behavior frees it.

global rt_init, actor_new, actor_send, actor_release, rt_shutdown

section .text
rt_init:
    ret

actor_new:
    xor eax, eax
    ret

actor_send:
    ret

actor_release:
    ret

rt_shutdown:
    ret
