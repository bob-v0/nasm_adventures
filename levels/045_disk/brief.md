# Level 45 — Disk

*Every operating system's first job is to load the rest of itself, 512 bytes at a time.*

## Lesson: two stages

The BIOS loads one sector, and 512 bytes isn't much. So real boot loaders (GRUB,
Windows' boot manager, Linux's old boot sector) put just enough in it to read more of
the disk, the **stage 2**, and jump there. This level's stage 2 is the game's: your boot
sector loads it.

## Lesson: int 13h

The BIOS's disk services are `int 0x13`. You pass the drive number in dl (0x80 = the
first hard disk, as the BIOS passed it to you), and the carry flag comes back set on
errors. There are two ways to say which sectors you want.

**CHS** (ah = 0x02) is the old way: by cylinder, head and sector, the disk's original
geometry. al = count, ch = cylinder, cl = sector (counted from **1**), dh = head, es:bx =
where to put them. Sector numbers above 63 and cylinders above 1023 don't fit, so CHS
reaches 8 GB at most.

**LBA** (ah = 0x42, the "extensions") numbers the sectors 0, 1, 2, ... You describe the
read with a **disk address packet** in memory, at ds:si:

```
dap:    db 16, 0            ; packet size, reserved
        dw 4                ; how many sectors
        dw 0x8000, 0x0000   ; buffer: offset, then segment
        dq 1                ; first LBA
```

Every BIOS since the late 1990s has it; check with ah = 0x41 if you must support older
ones.

## Gate

The stage 2 starts at LBA 1, right after your boot sector. Its first word is 0x5A2B and
its second the number of sectors it takes, itself included.

- Load all of it at 0000:8000.
- Enter it at 0000:8004 with dl = the boot drive. It prints the rest.

Tested with stage 2s of 1 to 60 sectors, and with another BIOS too (level 48's "odd").
