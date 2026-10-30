# Level 119 — Signals

*Ctrl+C, a segmentation fault, a child process exiting, a timer firing: the kernel
interrupts your program to tell it something.*

## Lesson: signals and handlers

A **signal** interrupts a program between two instructions. Each signal has a default
action (SIGINT and SIGSEGV terminate the process), or you install a **handler** with
`rt_sigaction` (13):

```
mov eax, 13             ; rt_sigaction(SIGINT, &act, NULL, 8)
mov edi, 2              ; SIGINT
lea rsi, [act]
xor edx, edx            ; don't want the old action
mov r10d, 8             ; size of the signal mask, in bytes
syscall

act: dq on_sigint       ; handler
     dq 0x04000000      ; flags: SA_RESTORER
     dq restorer        ; where the handler "returns" to
     dq 0               ; signals to block while it runs
```

When the signal arrives, the kernel saves **everything**: all registers, flags and the
signal mask go into a *signal frame* on your stack. Then it calls the handler as
`handler(signo, &siginfo, &ucontext)`, with the return address pointing at your
**restorer**. The restorer calls `rt_sigreturn` (15), which reloads everything from the
frame, so the interrupted code continues as if nothing happened. (C libraries supply the
restorer for you; that's what `SA_RESTORER` is about.)

## Lesson: faults are signals too

A bad memory access raises **SIGSEGV**, a division error **SIGFPE**. With a handler
installed, the handler runs instead of the program dying, and when it returns, the
faulting instruction runs **again**. Unless the handler changes where execution resumes:
the saved rip is in the ucontext, at offset **168** (`uc_mcontext.gregs[REG_RIP]`).
Editing it is how debuggers, JITs and some garbage collectors recover from faults on
purpose.

## Gate

1. Install a **SIGINT** handler that sets a flag. Spin in a loop of at most 100 000
   iterations, watching the flag. Print `caught SIGINT` if it was set, `no SIGINT` if
   the loop ran out.
2. Install a **SIGSEGV** handler, then read from address 0. The handler must make the
   program continue at a recovery label, which prints `recovered from SIGSEGV`.
3. Exit with status 0.

The tests send SIGINT at different moments (after at least 300 instructions), or not at
all. Every line ends with a newline. Constraint: at most 60 instructions.
