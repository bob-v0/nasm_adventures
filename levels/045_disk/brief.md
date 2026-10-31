# Level 45 — Disk

*Every operating system's first job is to load the rest of itself, 512 bytes at a time.*

## Lesson: two stages

The BIOS loads one sector. Real boot loaders (GRUB, Windows' boot manager, Linux's old
boot sector) put just enough in it to read more of the disk, the **stage 2**, and jump
there. This level's stage 2 is the game's: your boot sector loads it.

## Lesson: int 13h

The BIOS's disk services are `int 0x13`, with the drive number (0x80 = the first hard
disk, as the BIOS passed it in dl) and the carry flag set on errors.

**CHS** (ah = 0x02): the old way, by cylinder, head and sector, the disk's original
geometry. al = count, ch = cylinder, cl = sector (from **1**), dh = head, es:bx = where.
Sector numbers above 63 and cylinders above 1023 don't fit: CHS reaches 8 GB at most.

**LBA** (ah = 0x42, the "extensions"): sectors numbered 0, 1, 2, ..., described by a
**disk address packet** in memory, ds:si:

```
dap:    db 16, 0            ; packet size, reserved
        dw 4                ; how many sectors
        dw 0x8000, 0x0000   ; buffer: offset, then segment
        dq 1                ; first LBA
```

Every BIOS since the late 1990s has it; check with ah = 0x41 if you must support older
ones.

## Gate

Load the stage 2 (its sector count is in its header) at 0000:8000 and enter
it at 0000:8004 with dl = the boot drive. Tested with stage 2s of 1 to 60 sectors, and
with another BIOS (level 48).
