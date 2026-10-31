# Level 28 — CPUID & MSRs

*Before you switch a CPU into 64-bit mode, ask it whether it has one.*

## The task

The kernel starts, as in Arc XII, in 32-bit protected mode. Report what the CPU says
about itself on the serial port:

```
vendor: GenuineIntel
max leaf: 0x0000000d
max extended leaf: 0x80000008
pae: yes
apic: yes
long mode: yes
nx: yes
1g pages: no
efer: 0x00000800
```

Each test boots a different CPU: a different QEMU model, old and new, Intel and AMD,
some without long mode.

## Lesson: cpuid

`cpuid` is an instruction you ask questions with. Put a **leaf** number in eax; the
answer comes back in eax, ebx, ecx and edx.

| leaf | answer |
|---|---|
| 0 | eax: the highest basic leaf; ebx, edx, ecx: the vendor, 12 characters, in that order |
| 1 | edx bit 6: PAE; bit 9: an APIC |
| 0x80000000 | eax: the highest **extended** leaf |
| 0x80000001 | edx bit 20: NX; bit 26: 1 GiB pages; bit 29: long mode |

The extended leaves are a later addition. An old CPU may not have 0x80000001 at all,
and asking for a leaf it doesn't have isn't an error: an Intel CPU (and QEMU) answers
with its highest *basic* leaf instead, whose bits mean something else entirely. So check
the highest extended leaf first, as an unsigned number: on a CPU without extended leaves
even 0x80000000's answer is another leaf's data. Without 0x80000001 there is no long
mode, no NX and no 1 GiB pages.

## Lesson: MSRs

**Model-specific registers** are the CPU's configuration switches: hundreds of them,
numbered, read with `rdmsr` and written with `wrmsr`. ecx holds the number and edx:eax
the 64-bit value. You've used one already: IA32_APIC_BASE (0x1B) in level 33.

The one that matters now is **EFER** (0xC0000080):

| bit | name | |
|---|---|---|
| 0 | SCE | `syscall`/`sysret` (level 20) |
| 8 | LME | long mode enable (level 25) |
| 10 | LMA | long mode active (the CPU sets it) |
| 11 | NXE | the no-execute bit in page tables (level 26) |

Turn on NXE, but only if the CPU has NX. Setting a bit the CPU doesn't have is a #GP
fault, and with no IDT yet, that's a triple fault. Print EFER read back after writing,
or as it was if there's no NX.

A CPU without long mode gets, instead of the efer line:

```
this CPU can't run a 64-bit kernel
```

## Gate

The exact report for every CPU model the game boots.
