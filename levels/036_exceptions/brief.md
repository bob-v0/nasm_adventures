# Level 36 — Exceptions

*Divide by zero, an unknown opcode, a bad selector: the CPU's answer is always the same.
It interrupts itself, and goes where the IDT says.*

## Lesson: exceptions

Vectors 0-31 are reserved for the CPU's **exceptions**:

| vector | name | | vector | name |
|---|---|---|---|---|
| 0 | #DE divide error | | 10 | #TS invalid TSS |
| 1 | #DB debug | | 11 | #NP segment not present |
| 3 | #BP breakpoint (int3) | | 12 | #SS stack fault |
| 4 | #OF overflow (into) | | 13 | #GP general protection |
| 6 | #UD invalid opcode | | 14 | #PF page fault |
| 7 | #NM no FPU | | 17 | #AC alignment check |
| 8 | #DF double fault | | 18 | #MC machine check |

Some push an **error code** after eip: 8, 10-14, 17, 21, 29, 30. For #GP and its
relatives it's usually a selector (which descriptor was bad), or 0.

**Faults** push the eip of the faulting instruction, so returning retries it (that's how
a page fault handler can fix the problem and go on). **Traps** (#BP, #OF) push the eip
after it. **Aborts** (#DF, #MC) can't be returned from.

## Lesson: the IDT

In protected mode the interrupt table is the **IDT**: up to 256 8-byte **gates**, found
through IDTR (`lidt [pointer]`, like lgdt).

```
 bytes 0-1  offset 0-15        bytes 4-5  type: P DPL 0 1110 (0x8E00: an interrupt gate)
 bytes 2-3  code selector      bytes 6-7  offset 16-31
```

An **interrupt gate** clears IF on entry; a **trap gate** (0x8F) doesn't. The handler
runs with cs from the gate, and finds `eflags, cs, eip` (and maybe an error code) on its
stack. Without a valid gate, the CPU raises #GP, then #DF, then resets: level 35.

## Lesson: modules again

The game's code arrives as module 0 (level 37). Copy it to 0x400000 (it was assembled for
that address) with `rep movsb` and `call 0x400000`. It prints a line and then faults.

## Gate

An IDT for vectors 0-31; for whichever exception the module causes, report the vector,
the pushed eip and, if there is one, the error code.
