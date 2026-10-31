# Level 119 — Signals

*Ctrl+C, a segmentation fault, a child process exiting, a timer firing: the kernel
interrupts your program to tell it something.*

## Lesson: signals and handlers

A **signal** is a notification from the kernel that interrupts a program between two
instructions. Each signal has a number (SIGINT, the one Ctrl+C sends, is 2) and a
default action: SIGINT and SIGSEGV terminate the process. Or you install a **handler**,
a function of yours that runs instead, with `rt_sigaction` (13):

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

Here is what happens when the signal arrives:

```
your code runs ... ── SIGINT ──┐
                               │ kernel saves EVERYTHING in a signal frame on your stack:
                               │   all registers, flags, rip, the signal mask
                               │ kernel calls handler(signo, &siginfo, &ucontext)
                               │ handler runs, then ret ...
                               │ ... into your restorer: mov eax, 15 / syscall
                               │ rt_sigreturn (15) reloads everything from the frame
your code continues ◄──────────┘   as if nothing happened
```

The **restorer** is the address the handler returns to; it only calls `rt_sigreturn`.
C libraries supply it for you; that's what `SA_RESTORER` is about.

## Lesson: faults are signals too

A bad memory access raises **SIGSEGV**, a division error **SIGFPE**. With a handler
installed, the handler runs instead of the program dying, and when it returns, the
faulting instruction runs **again**, and faults again.

Unless the handler changes where execution resumes. The saved rip is part of the
ucontext, at offset **168** (`uc_mcontext.gregs[REG_RIP]`). Whatever the handler writes
there is where `rt_sigreturn` continues. Debuggers, JITs and some garbage collectors
recover from faults on purpose this way.

## Gate

1. Install a **SIGINT** handler that sets a flag. Spin in a loop of at most 100 000
   iterations, watching the flag. Print `caught SIGINT` if it was set, `no SIGINT` if
   the loop ran out.
2. Install a **SIGSEGV** handler, then read from address 0. The handler must make the
   program continue at a recovery label, which prints `recovered from SIGSEGV`.
3. Exit with status 0.

The tests send SIGINT at different moments (after at least 300 instructions), or not at
all. Every line ends with a newline. Constraint: at most 60 instructions.
