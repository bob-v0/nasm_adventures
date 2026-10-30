"""Processes in the emulated kernel: fork, execve, wait4, pipes, dup2, the scheduler."""

import pytest

from ring.build import build
from ring.emu import Machine
from ring.kernel import Injection, Kernel
from ring.userland import install_userland

PIPELINE = r"""
; echo one two three | wc   (then report both children's statuses)
global _start
section .text
_start:
    mov eax, 22                 ; pipe(fds)
    lea rdi, [fds]
    syscall
    mov eax, 57                 ; fork
    syscall
    test rax, rax
    jz writer
    mov r12, rax
    mov eax, 57
    syscall
    test rax, rax
    jz reader
    mov r13, rax
    mov eax, 3                  ; the parent closes both ends
    mov edi, [fds]
    syscall
    mov eax, 3
    mov edi, [fds + 4]
    syscall
    mov eax, 61                 ; wait4(writer, &status, 0, 0)
    mov rdi, r12
    lea rsi, [status]
    xor edx, edx
    xor r10d, r10d
    syscall
    mov eax, 61
    mov rdi, r13
    lea rsi, [status + 4]
    xor edx, edx
    xor r10d, r10d
    syscall
    mov eax, 60
    mov edi, [status + 4]
    shr edi, 8
    add edi, [status]
    syscall
writer:
    mov eax, 33                 ; dup2(fds[1], 1)
    mov edi, [fds + 4]
    mov esi, 1
    syscall
    call close_both
    mov eax, 59                 ; execve("/bin/echo", echo_argv, envp)
    lea rdi, [echo_path]
    lea rsi, [echo_argv]
    lea rdx, [envp]
    syscall
    mov eax, 60
    mov edi, 127
    syscall
reader:
    mov eax, 33                 ; dup2(fds[0], 0)
    mov edi, [fds]
    xor esi, esi
    syscall
    call close_both
    mov eax, 59
    lea rdi, [wc_path]
    lea rsi, [wc_argv]
    lea rdx, [envp]
    syscall
    mov eax, 60
    mov edi, 127
    syscall
close_both:
    mov eax, 3
    mov edi, [fds]
    syscall
    mov eax, 3
    mov edi, [fds + 4]
    syscall
    ret
section .data
echo_path: db "/bin/echo", 0
wc_path:   db "/bin/wc", 0
a1: db "one", 0
a2: db "two", 0
a3: db "three", 0
echo_argv: dq echo_path, a1, a2, a3, 0
wc_argv:   dq wc_path, 0
envp:      dq 0
section .bss
fds: resd 2
status: resd 2
"""


def run(tmp_path, source, files=None, userland=True, inject=None, steps=200_000):
    (tmp_path / "s.asm").write_text(source)
    b = build(tmp_path / "s.asm", tmp_path / "b", "program")
    k = Kernel(files=files or {}, inject=Injection.from_dict(inject, "t"))
    if userland:
        install_userland(k)
    m = Machine(b, kernel=k)
    m.run(steps)
    return m


def test_pipeline(tmp_path):
    m = run(tmp_path, PIPELINE)
    assert m.state == "exited", m.fault
    assert bytes(m.stdout) == b"1\n"
    assert m.exit_code == 0        # echo exited 0, wc exited 0
    assert m.kernel.procs.keys() == {1000}     # both children were reaped


@pytest.mark.parametrize("quantum", [1, 3, 17, 500])
def test_pipeline_any_interleaving(tmp_path, quantum):
    m = run(tmp_path, PIPELINE, inject={"quantum": quantum})
    assert (m.state, bytes(m.stdout)) == ("exited", b"1\n"), m.fault


def test_forgotten_write_end_deadlocks(tmp_path):
    # The parent keeps its write end open and waits for the reader: nobody can finish.
    src = PIPELINE.replace("    mov eax, 3                  ; the parent closes both ends\n"
                           "    mov edi, [fds]\n    syscall\n    mov eax, 3\n    mov edi, [fds + 4]\n"
                           "    syscall\n", "")
    src = src.replace("    mov rdi, r12\n    lea rsi, [status]", "    mov rdi, r13\n    lea rsi, [status]")
    m = run(tmp_path, src)
    assert m.state == "fault" and "deadlock" in m.fault, (m.state, m.fault)


EXIT_STATUS = r"""
global _start
section .text
_start:
    mov eax, 57
    syscall
    test rax, rax
    jnz parent
    mov eax, 59                 ; the child runs /bin/{prog}
    lea rdi, [path]
    lea rsi, [argv]
    xor edx, edx
    syscall
    mov edi, eax                ; execve failed: exit with -errno's low byte
    neg edi
    mov eax, 60
    syscall
parent:
    mov eax, 61
    mov rdi, -1
    lea rsi, [status]
    xor edx, edx
    xor r10d, r10d
    syscall
    mov r15, rax                ; the reaped pid
    mov eax, 61                 ; a second wait4: no children left
    mov rdi, -1
    xor esi, esi
    xor edx, edx
    xor r10d, r10d
    syscall
    mov r14, rax
    mov eax, 60
    mov edi, [status]
    syscall
section .data
path: db "/bin/{prog}", 0
argv: dq path, 0
section .bss
status: resd 1
"""


@pytest.mark.parametrize("prog,status", [("true", 0), ("false", 1 << 8), ("exit3", 3 << 8),
                                         ("crash", 11), ("missing", 2 << 8)])
def test_wait_status(tmp_path, prog, status):
    m = run(tmp_path, EXIT_STATUS.replace("{prog}", prog))
    assert m.state == "exited", m.fault
    assert m.exit_code == status & 0xFF
    assert m.reg("r15") == 1001 and m.reg("r14") == (-10) & (2**64 - 1)   # ECHILD


def test_fork_copies_memory(tmp_path):
    src = r"""
global _start
section .text
_start:
    mov qword [value], 5
    mov eax, 57
    syscall
    test rax, rax
    jnz parent
    mov qword [value], 99       ; only the child's copy changes
    mov eax, 60
    mov edi, [value]
    syscall
parent:
    mov eax, 61
    mov rdi, -1
    lea rsi, [status]
    xor edx, edx
    xor r10d, r10d
    syscall
    mov eax, 60
    mov rdi, [value]
    mov ecx, [status]
    shr ecx, 8
    add edi, ecx
    syscall
section .bss
value: resq 1
status: resd 1
"""
    m = run(tmp_path, src, userland=False)
    assert (m.state, m.exit_code) == ("exited", 104)


def test_step_through_wait(tmp_path):
    """Single-stepping the parent lets the children run while it waits."""
    (tmp_path / "s.asm").write_text(PIPELINE)
    b = build(tmp_path / "s.asm", tmp_path / "b", "program")
    k = Kernel()
    install_userland(k)
    m = Machine(b, kernel=k, record=True)
    n = 0
    while not m.finished and n < 10_000:
        m.step()
        n += 1
    assert (m.state, bytes(m.stdout)) == ("exited", b"1\n"), m.fault


def test_signal_to_self_resumes_after_the_syscall(tmp_path):
    src = r"""
global _start
section .text
_start:
    mov eax, 13                 ; rt_sigaction(SIGUSR1, &act, 0, 8)
    mov edi, 10
    lea rsi, [act]
    xor edx, edx
    mov r10d, 8
    syscall
    mov eax, 39
    syscall
    mov edi, eax
    mov eax, 62                 ; kill(getpid(), SIGUSR1)
    mov esi, 10
    syscall
    mov ebx, 7                  ; must run exactly once, after the handler
    mov eax, 60
    mov edi, ebx
    add edi, [count]
    syscall
handler:
    add dword [count], 10
    ret
restorer:
    mov eax, 15
    syscall
section .data
act: dq handler, 0x04000000, restorer, 0
count: dd 0
"""
    m = run(tmp_path, src, userland=False)
    assert (m.state, m.exit_code) == ("exited", 17), m.fault


INTERRUPTED_READ = r"""
global _start
section .text
_start:
    mov eax, 13                 ; rt_sigaction(SIGUSR1, &act, 0, 8)
    mov edi, 10
    lea rsi, [act]
    xor edx, edx
    mov r10d, 8
    syscall
    mov eax, 22
    lea rdi, [fds]
    syscall
    mov eax, 57
    syscall
    test rax, rax
    jz child
    xor eax, eax                ; read(fds[0], buf, 1): the child signals, then writes
    mov edi, [fds]
    lea rsi, [buf]
    mov edx, 1
    syscall
    mov edi, eax                ; exit(read's result + 100 * handled)
    imul ecx, [handled], 100
    add edi, ecx
    mov eax, 60
    syscall
child:
    mov ecx, 100                ; give the parent time to block in read
.spin:
    dec ecx
    jnz .spin
    mov eax, 110                ; kill(getppid(), SIGUSR1)
    syscall
    mov edi, eax
    mov eax, 62
    mov esi, 10
    syscall
    mov ecx, 100                ; and time to handle the signal
.spin2:
    dec ecx
    jnz .spin2
    mov eax, 1                  ; write(fds[1], "x", 1)
    mov edi, [fds + 4]
    lea rsi, [buf]
    mov edx, 1
    syscall
    mov eax, 60
    xor edi, edi
    syscall
handler:
    inc dword [handled]
    ret
restorer:
    mov eax, 15
    syscall
section .data
act: dq handler, 0x04000000 | {flags}, restorer, 0
handled: dd 0
section .bss
fds: resd 2
buf: resb 1
"""


@pytest.mark.parametrize("flags,status", [(0, (100 - 4) & 0xFF),        # EINTR
                                          (0x10000000, 101)])          # SA_RESTART: 1 byte
def test_signal_interrupts_blocked_read(tmp_path, flags, status):
    m = run(tmp_path, INTERRUPTED_READ.replace("{flags}", str(flags)), userland=False,
            inject={"quantum": 5})
    assert (m.state, m.exit_code) == ("exited", status), m.fault


def test_sigpipe(tmp_path):
    """Writing to a pipe nobody reads kills the writer with SIGPIPE."""
    src = r"""
global _start
section .text
_start:
    mov eax, 22
    lea rdi, [fds]
    syscall
    mov eax, 3
    mov edi, [fds]
    syscall
    mov eax, 1
    mov edi, [fds + 4]
    lea rsi, [fds]
    mov edx, 1
    syscall
    mov eax, 60
    xor edi, edi
    syscall
section .bss
fds: resd 2
"""
    m = run(tmp_path, src, userland=False)
    assert (m.state, m.term_signal) == ("killed", 13)


def test_getdents64_lists_a_directory(tmp_path):
    src = r"""
global _start
section .text
_start:
    mov eax, 2
    lea rdi, [dir]
    mov esi, 0o200000
    syscall
    mov r12, rax
    mov eax, 217                ; getdents64(fd, buf, 4096)
    mov rdi, r12
    lea rsi, [buf]
    mov edx, 4096
    syscall
    mov r13, rax
    mov eax, 217                ; then 0: the end
    mov rdi, r12
    lea rsi, [buf + 4096]
    mov edx, 4096
    syscall
    mov r14, rax
    mov eax, 60
    xor edi, edi
    syscall
section .data
dir: db "/work/d", 0
section .bss
buf: resb 8192
"""
    m = run(tmp_path, src, userland=False,
            files={"/work/d/b.txt": "x", "/work/d/a": "y", "/work/d/sub/c": "z"})
    assert m.state == "exited", m.fault
    n, data = m.reg("r13"), m.read(m.build.symbols["buf"], m.reg("r13"))
    names, off = [], 0
    while off < n:
        reclen, dtype = int.from_bytes(data[off + 16:off + 18], "little"), data[off + 18]
        names.append((data[off + 19:off + reclen].split(b"\0")[0].decode(), dtype))
        off += reclen
    assert names == [(".", 4), ("..", 4), ("a", 8), ("b.txt", 8), ("sub", 4)]
    assert m.reg("r14") == 0


# ---- the same programs on the real kernel ----------------------------------------------------

from .conftest import needs_native  # noqa: E402


def _native(tmp_path, source, argv=None, stdin=b""):
    """Build `source` with /bin/X pointing at the game's utilities in tmp_path/bin."""
    import subprocess
    from ring.userland import programs
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for name, image in programs().items():
        (bindir / name).write_bytes(image)
        (bindir / name).chmod(0o755)
    src = source.replace('"/bin/', f'"{bindir}/')
    (tmp_path / "n.asm").write_text(src)
    b = build(tmp_path / "n.asm", tmp_path / "nb", "program")
    import resource

    def no_core_dumps():   # otherwise a crash's wait status also has bit 7 (core dumped) set
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return subprocess.run([str(b.elf)] + (argv or []), input=stdin, capture_output=True,
                          timeout=10, cwd=tmp_path, preexec_fn=no_core_dumps)


@needs_native
def test_pipeline_matches_native(tmp_path):
    r = _native(tmp_path, PIPELINE)
    m = run(tmp_path, PIPELINE)
    assert (r.stdout, r.returncode) == (bytes(m.stdout), m.exit_code) == (b"1\n", 0)


@needs_native
@pytest.mark.parametrize("prog", ["true", "false", "exit3", "crash", "missing"])
def test_wait_status_matches_native(tmp_path, prog):
    src = EXIT_STATUS.replace("{prog}", prog)
    r = _native(tmp_path, src)
    m = run(tmp_path, src)
    assert r.returncode == m.exit_code


@needs_native
def test_directory_walk_matches_native(tmp_path):
    """Level 112's reference on a real directory: same lines (real order is unspecified)."""
    import subprocess
    from ring.level import all_levels
    tree = {"a.txt": "one two\n", "sub/b.txt": " three\tfour \n\nfive", "sub/deep/c": "",
            "z": "six " * 2000}
    root = tmp_path / "tree"
    for rel, text in tree.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    (root / "link").symlink_to(root / "a.txt")
    lv = all_levels()[112]
    b = build(lv.reference, tmp_path / "b112", "program")
    native = subprocess.run([str(b.elf), "tree"], capture_output=True, timeout=10, cwd=tmp_path)
    k = Kernel(files={f"/work/tree/{rel}": text for rel, text in tree.items()}
               | {"/work/tree/link": {"symlink": "/work/tree/a.txt"}})
    m = Machine(b, kernel=k, argv=["./solution", "tree"])
    m.run(2_000_000)
    assert native.returncode == m.exit_code == 0
    assert sorted(native.stdout.splitlines()) == sorted(bytes(m.stdout).splitlines())
