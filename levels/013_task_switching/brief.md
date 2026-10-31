# Level 13 — Task Switching

*One CPU, several programs, each sure it has the machine to itself. The trick is a
function that returns in a different program from the one that called it.*

## The task

Every module is a program (an ELF file). They all run "at once": each until it calls
**sched_yield** (system call 24), then the next one, round robin, until every one has
exited (`all tasks done`). When a task's turn comes back, everything must be as it left it:
its registers (all but rax, rcx and r11, as for any system call), its stack, its memory.

Each task has an address space of its own (level 18) and a **kernel stack** of its own,
one frame. The starter loads the tasks and handles the system calls. Yours:
`prepare_stack`, `schedule` and `switch_to`.

## Lesson: switching is switching kernel stacks

When a task calls `sched_yield`, its system call has already pushed its user state (rip,
rflags, rsp, registers) onto its kernel stack. All that's left of it is that stack and the
kernel's position in it. So a context switch is little more than:

```
switch_to:                  ; from, to
    push rbx, rbp, r12-r15  ; what a called function must keep
    tasks[from].ksp = rsp
    cr3 = tasks[to].space
    TSS.RSP0 = tasks[to].stack's top    ; where ITS next entry from ring 3 lands
    rsp = tasks[to].ksp
    pop r15-r12, rbp, rbx
    ret                     ; ...into wherever `to` called switch_to
```

![Two tasks' kernel stacks: switch_to saves one rsp and loads the other](switch.svg)

## Lesson: a stack that was never used

A brand-new task never called switch_to, so there's nothing for the `ret` to return to.
`prepare_stack` fakes it: at the top of the new kernel stack goes the iretq frame into
the program (ss, rsp, rflags, cs, rip). Below that goes the address of `first_run`, and
below that six zeros for the registers switch_to pops. The first switch to the task
"returns" into first_run, which does the `iretq`.

## Gate

Every test's tasks, their output in turn, their registers kept, their exits.
