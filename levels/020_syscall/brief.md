# Level 20 — syscall/sysret

*`int 0x80` goes through the IDT, a gate check, a stack switch and five pushes. A system
call is the most frequent trip into a kernel. It got its own instruction.*

## The task

Replace level 21's `int 0x80` with **`syscall`**, the way Linux programs call Linux:
rax is the call's number, its arguments go in rdi, rsi and rdx, and the result comes back
in rax. Errors are negative numbers.

| rax | call | |
|---|---|---|
| 1 | write(fd, buffer, count) | print the bytes; return count, or −14 (EFAULT) if the buffer isn't the program's |
| 60 | exit(status) | `user program exited with status N`, then halt |
| 158 | arch_prctl(0x1001, address) | set the program's gs base; return 0 (other codes: −22) |
| other | | −38 (ENOSYS) |

The tests' programs check what programs rely on:
- every register except rax, rcx and r11 comes back unchanged, and rsp too;
- a program that left the direction flag set still has its text printed forwards;
- a kernel address as the buffer gets −14, not the kernel's memory;
- the gs base a program sets survives the calls it makes afterwards.

## Lesson: syscall and sysret

`syscall` jumps to the address in the **LSTAR** MSR, in ring 0, with cs and ss from
**STAR**. It saves the program's rip in **rcx** and its rflags in **r11**, and clears
the rflags bits set in **SFMASK**. `sysret` goes back: rip from rcx, rflags from r11,
ring 3. That's all it does. In particular, **it doesn't switch stacks**: rsp still points
at the program's stack, which the kernel must not trust, or even use.

## Lesson: swapgs

So where is the kernel's stack? The CPU keeps two gs bases: **GS_BASE**, in use, and
**KERNEL_GS_BASE**, waiting. `swapgs` exchanges them. While a program runs, GS_BASE is
the program's own and KERNEL_GS_BASE points at the kernel's **per-CPU data**. The entry
point's first instruction swaps them, and then `gs:` reaches the kernel's data:

```
syscall_entry:
    swapgs                  ; gs = per-CPU data
    mov [gs:8], rsp         ; the program's rsp
    mov rsp, [gs:0]         ; the kernel stack
    ...
    mov rsp, [gs:8]
    swapgs                  ; gs = the program's again
    o64 sysret
```

(Without `o64`, `sysret` returns to 32-bit code.) Interrupts are off for all of this,
because SFMASK clears IF. Level 19 is about why that matters.

## Lesson: never trust a pointer

`write` is handed an address by the program. If the kernel copies from it without
checking, any program can read the kernel's memory, or another program's, by asking for
it. The buffer must lie entirely inside the program's memory, here USER to USER_TOP.
Watch out for an address plus a count that wraps around zero.

## Gate

Every program's output and exit status, exactly.
