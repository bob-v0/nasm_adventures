# Level 112 — Directories & mmap

*Two more ways to look at files: a directory is a file full of names, and any file can
become memory.*

## Lesson: reading a directory

Open a directory like a file (`O_DIRECTORY`, 0o200000, makes `open` fail if it isn't
one), then call `getdents64(fd, buf, size)` (syscall 217). It fills `buf` with as many
**records** as fit and returns how many bytes it wrote; 0 means you've seen them all.
Each record is a `struct linux_dirent64`, and records have different lengths because
names do:

| offset | size | field |
|---|---|---|
| 0 | 8 | `d_ino`: the inode number (the file's id inside the filesystem) |
| 8 | 8 | `d_off`: a cookie for the next record (you don't need it) |
| 16 | 2 | **`d_reclen`**: this record's length, so `+ d_reclen` is the next one |
| 18 | 1 | **`d_type`**: 4 = directory (`DT_DIR`), 8 = regular file (`DT_REG`), 10 = symlink |
| 19 | … | **`d_name`**: the name, NUL-terminated (padded to a multiple of 8) |

So you walk the buffer by adding each record's `d_reclen`, until you reach the byte
count `getdents64` returned. For example (19 bytes of header, the name and its NUL,
rounded up to a multiple of 8):

```
offset:  0          24          48                  80
         [ "."    ] [ ".."    ] [ "notes.txt"     ] [ "sub"   ] ...
         reclen 24  reclen 24   reclen 32           reclen 24
```

Every directory lists `.` (itself) and `..` (its parent). Skip them, or a recursive walk
never ends. The order is **whatever the filesystem stores**. On real Linux that's usually
a hash order, not alphabetical; `ls` sorts. (Some filesystems report `d_type` 0,
unknown, and then you need `stat`. The game's kernel always fills it in.)

## Lesson: recursion with your own stack frames

A walk goes depth first: when an entry is a directory, walk it, then carry on with the
rest of the current one. Each level of the recursion needs its **own** `getdents64`
buffer (the parent's records must survive the child's walk). The stack is the natural
place for it: `sub rsp, 1024` on entry, `add rsp, 1024` before `ret`. The path, on the
other hand, can be one global buffer: append `/name` before you descend, and cut it back
afterwards.

## Lesson: mapping a file

Instead of copying a file into a buffer with `read`, you can ask the kernel to make the
file *appear* in memory. `mmap(addr, length, prot, flags, fd, offset)` (syscall 9) with a
descriptor instead of −1 maps the **file's contents** into memory. The bytes appear at the returned address,
and pages are loaded from the file only when touched (each first touch is a page fault
the kernel handles silently). With `PROT_READ` (1) and `MAP_PRIVATE` (2) you can read
the file as an array: no `read` loop, no buffer, no copying. Databases, linkers and
`ld.so` work this way.

You need the file's size first: `fstat(fd, &st)` puts `st_size` at offset **48**.
`mmap` with length **0 fails** (`-EINVAL`), so an empty file needs its own path.
`munmap(addr, length)` (11) removes the mapping. You can close the descriptor right after
mapping; the mapping keeps the file alive.

## Gate

`argv[1]` is a directory. Visit **everything** in it and all its subdirectories, in the
order `getdents64` returns the entries, depth first. Skip `.`, `..`, every name that
starts with `.`, symlinks, and anything that is neither a directory nor a regular file.
For each regular file:

1. map it with `mmap` (don't `read` it) and count its **words**: runs of bytes other
   than space, tab and newline;
2. print `PATH: N` and a newline, where PATH is `argv[1]`, then `/name` for each level
   (e.g. `docs/sub/notes.txt`);
3. unmap it and close it.

Finally print `total: N` (all the words) and exit with 0. The tests check that every
non-empty file was mapped and unmapped, that nothing was `read`, and that only
descriptors 0, 1 and 2 are open at the end. Constraint: at most 160 instructions.
