# Level 36 — Exceptions

*Divide by zero, an unknown opcode, a bad selector: the CPU's answer is always the same.
It interrupts itself, and goes where the IDT says.*

## Lesson: exceptions

When an instruction can't be completed, the CPU raises an **exception**: it interrupts
itself, through one of the vectors 0–31, which are reserved for this:

| vector | name | | vector | name |
|---|---|---|---|---|
| 0 | #DE divide error | | 10 | #TS invalid TSS |
| 1 | #DB debug | | 11 | #NP segment not present |
| 3 | #BP breakpoint (int3) | | 12 | #SS stack fault |
| 4 | #OF overflow (into) | | 13 | #GP general protection |
| 6 | #UD invalid opcode | | 14 | #PF page fault |
| 7 | #NM no FPU | | 17 | #AC alignment check |
| 8 | #DF double fault | | 18 | #MC machine check |

Some exceptions push an **error code** after eip: vectors 8, 10–14, 17, 21, 29 and 30.
For #GP and its relatives it's usually a selector (which descriptor was bad), or 0.

Which eip gets pushed depends on the kind of exception:

- **Faults** push the eip of the faulting instruction, so returning retries it. That's
  how a page fault handler can fix the problem and carry on.
- **Traps** (#BP, #OF) push the eip of the instruction after it.
- **Aborts** (#DF, #MC) can't be returned from.

## Lesson: the IDT

In protected mode the interrupt table is the **IDT**: up to 256 8-byte **gates**, found
through the IDTR register (`lidt [pointer]`, with the same 6-byte pointer as lgdt).

```
 bytes 0-1  offset 0-15        bytes 4-5  type: P DPL 0 1110 (0x8E00: an interrupt gate)
 bytes 2-3  code selector      bytes 6-7  offset 16-31
```

![An interrupt gate, byte by byte, and its type byte](gate.svg)

An **interrupt gate** clears IF on entry; a **trap gate** (0x8F) doesn't. The handler
runs with cs from the gate, and finds this on its stack:

```
without an error code:          with an error code:
  [esp]      eip                  [esp]       error code
  [esp + 4]  cs                   [esp + 4]   eip
  [esp + 8]  eflags               [esp + 8]   cs
                                  [esp + 12]  eflags
```

Without a valid gate, the CPU raises #GP, then #DF, then resets: level 35.

## Lesson: modules again

The game's code arrives as module 0 (level 37). Copy it to 0x400000, the address it was
assembled for (`rep movsb`), and `call 0x400000`. It prints a line, then causes an
exception.

## Gate

Load your own GDT (level 39's), then an IDT with a handler for each of the 32 exception
vectors. Run module 0 as above. When the exception comes, send one line to COM1 and
halt:

```
exception <vector, decimal> at 0x<the eip the CPU pushed, 8 hex digits>
```

For the exceptions that push an error code, add `, error code 0x<8 hex digits>` before
the CR LF. Hex digits are lowercase. Examples:

```
exception 0 at 0x00400027
exception 13 at 0x00400022, error code 0x0000fff8
```
