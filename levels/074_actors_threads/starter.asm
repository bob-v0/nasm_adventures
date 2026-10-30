; Level 74 — Actors Across Threads
;
; Arc VI's actors, now on several worker threads. Write the heart of the runtime:
;
;   actor_send(actor, msg)   called by any thread, any time: put msg in the actor's
;                            mailbox; if the actor isn't scheduled yet, schedule it
;                            with runq_push(actor) (a worker will call actor_run)
;   actor_run(actor)         called by a worker: hand the actor's messages, oldest
;                            first, to behavior(actor, msg), then return. While it runs,
;                            no other worker may run the same actor; a message that
;                            arrives meanwhile must not be lost.
;
; actor: 128 zeroed bytes; +0 and +8 are yours (the harness uses +64 onwards).
; msg: dq next, dq value. behavior frees it.

global actor_send, actor_run
extern runq_push, behavior

section .text
actor_send:
    ret

actor_run:
    ret
