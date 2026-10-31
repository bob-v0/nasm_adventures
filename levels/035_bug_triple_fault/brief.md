# Level 35 — Bug: Triple Fault Hunt ◆◆

*No error message. No output. The screen flashes and the machine starts over, faster than
you can read anything.*

## Symptoms

This is level 36's kernel, as somebody else wrote it. It loads a GDT and an IDT, copies
the game's module and calls it; the module prints a line and causes an exception. The
kernel should report it. Instead the PC resets, every time.

## Background: how a PC dies

When an exception can't be delivered (the gate is missing, beyond the IDT's limit, not
present, or points at something that isn't code), the CPU raises a new exception about
that: usually #GP. If delivering *that* fails too, it raises **#DF**, the double fault.
If #DF can't be delivered either, there is nothing left to try: the CPU **shuts down**,
and the PC's chipset resets it. That's a **triple fault**, and from the outside it looks
like an instant reboot with no message at all.

On real hardware you'd be guessing. QEMU can log every exception (`-d int`), and the
game reads that log back for you: the **fault explainer** in the test report lists the
exceptions before the reset, decodes their error codes, and looks at the IDT register to
say why delivery failed. Read it from the top: the first exception is the real event,
the rest is the CPU failing to report it.

Run it yourself in {{terminal}}:
`qemu-system-i386 -kernel solution.elf -d int,cpu_reset -no-reboot -display none` and
look for `check_exception` and `v=` lines.

## Gate

Make the kernel report every exception the module causes, as in level 36. At most 4
changed lines.
