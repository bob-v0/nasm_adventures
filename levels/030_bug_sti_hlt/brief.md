# Level 30 — Bug: The sti;hlt Race ◆◆◆

*The interrupt came. The kernel saw it. And then it went to sleep, waiting for it.*

## Symptoms

A driver's main loop in miniature: start an I/O request, then until the device's
completion interrupt sets a flag: show "waiting for request N" on the screen and sleep
with `hlt`. 50 requests in all. The "device" is the APIC timer
in one-shot mode, interrupting once, a little later each time. With long delays all 50
requests complete. With shorter ones the machine just sleeps, forever, with the last
completion interrupt already handled.

## Background: sleeping on one CPU

`hlt` stops the CPU until the next interrupt. An idle loop therefore looks like
"is there work? if not, hlt". The trouble is the gap between the check and the hlt. If the
interrupt that brings the work arrives in that gap, the handler runs, the flag is set, and
then the code goes on to the hlt it had already decided on, to wait for an interrupt
that has already come and gone. If nothing else interrupts, it waits forever.

It's a **lost wakeup**: level 79's bug between threads, here between a program and its own
interrupt handler.

## Background: the interrupt shadow

x86 provides exactly the tool for this. `sti` enables interrupts only **after the next
instruction**: the **interrupt shadow**. So in

```
cli             ; no interrupts while we look
cmp ...         ; is there work?
jne work
sti             ; interrupts on, but not yet...
hlt             ; ...only once hlt has begun: a pending one wakes it at once
```

an interrupt that became pending during the check is delivered when hlt has started,
and ends the sleep. Every operating system's idle loop is built on this.

## Gate

Find a delay that hangs the original (`;! witness delay = N`), and fix it so every delay
the game tries completes all 50 requests. At most 6 changed lines.
