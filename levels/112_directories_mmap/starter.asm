; Level 112 — Directories & mmap
;
; argv[1] is a directory. Visit every entry in it and in all its subdirectories
; (skip "." and "..", names starting with ".", symlinks, and anything that isn't a
; directory or a regular file), in the order getdents64 returns them, depth first:
; a subdirectory's contents come right where the subdirectory is listed.
;
; For each regular file, map it with mmap (don't read() it) and count its words
; (runs of bytes other than space, tab and newline). Print
;     PATH: N
; where PATH is argv[1] + "/" + ... + name. At the end, print "total: N" and exit 0.

global _start

section .text
_start:
    ; TODO
    mov eax, 60
    xor edi, edi
    syscall
