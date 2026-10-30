"""Events in the emulated kernel: sockets with scripted clients, epoll, timerfd,
non-blocking I/O, virtual time."""

import pytest

from ring.build import build
from ring.emu import Machine
from ring.kernel import Injection, Kernel

ECHO_SERVER = r"""
; An epoll echo server on 127.0.0.1:7000.
global _start
section .text
_start:
    mov eax, 41                 ; socket(AF_INET, SOCK_STREAM | SOCK_NONBLOCK, 0)
    mov edi, 2
    mov esi, 1 | 0o4000
    xor edx, edx
    syscall
    mov r12, rax
    mov eax, 54                 ; setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, 4)
    mov rdi, r12
    mov esi, 1
    mov edx, 2
    lea r10, [one]
    mov r8d, 4
    syscall
    mov eax, 49                 ; bind(fd, &addr, 16)
    mov rdi, r12
    lea rsi, [addr]
    mov edx, 16
    syscall
    test rax, rax
    js fail
    mov eax, 50                 ; listen(fd, 16)
    mov rdi, r12
    mov esi, 16
    syscall
    mov eax, 291                ; epoll_create1(0)
    xor edi, edi
    syscall
    mov r13, rax
    mov rsi, r12
    call watch
loop:
    mov eax, 232                ; epoll_wait(ep, events, 16, -1)
    mov rdi, r13
    lea rsi, [events]
    mov edx, 16
    mov r10, -1
    syscall
    mov r14, rax
    xor r15d, r15d
.event:
    cmp r15, r14
    jae loop
    imul rax, r15, 12
    mov rbx, [events + rax + 4]   ; data = the fd (struct epoll_event is packed: 12 bytes)
    inc r15
    cmp rbx, r12
    jne .client
    mov eax, 288                ; accept4(listener, 0, 0, SOCK_NONBLOCK)
    mov rdi, r12
    xor esi, esi
    xor edx, edx
    mov r10d, 0o4000
    syscall
    test rax, rax
    js .event
    mov rsi, rax
    call watch
    jmp .event
.client:
    xor eax, eax                ; read(fd, buf, 4096)
    mov rdi, rbx
    lea rsi, [buf]
    mov edx, 4096
    syscall
    cmp rax, -11                ; EAGAIN: nothing after all
    je .event
    test rax, rax
    jle .close
    mov rdx, rax                ; write it back (small: it fits)
    mov eax, 1
    mov rdi, rbx
    lea rsi, [buf]
    syscall
    jmp .event
.close:
    mov eax, 3
    mov rdi, rbx
    syscall
    jmp .event

watch:                          ; epoll_ctl(ep, ADD, rsi, {EPOLLIN, rsi})
    mov dword [ev], 1
    mov [ev + 4], rsi
    mov eax, 233
    mov rdi, r13
    mov rdx, rsi
    mov esi, 1
    lea r10, [ev]
    syscall
    ret
fail:
    mov eax, 60
    mov edi, 1
    syscall

section .data
one:  dd 1
addr: dw 2                      ; AF_INET
      db 7000 >> 8, 7000 & 0xFF ; the port, big-endian
      db 127, 0, 0, 1
      times 8 db 0
section .bss
ev:     resb 12
events: resb 12 * 16
buf:    resb 4096
"""


def client(name, lines, at=0, close="close"):
    steps = []
    for ln in lines:
        steps += [{"send": ln}, {"expect": ln}]
    steps.append({close: True})
    return {"name": name, "connect": 7000, "at": at, "steps": steps}


def run(tmp_path, source, peers, steps=2_000_000, inject=None):
    (tmp_path / "s.asm").write_text(source)
    b = build(tmp_path / "s.asm", tmp_path / "b", "program")
    k = Kernel(inject=Injection.from_dict({"peers": peers, **(inject or {})}, "t"))
    m = Machine(b, kernel=k)
    m.run(steps)
    return m


def test_echo_server_serves_interleaved_clients(tmp_path):
    peers = [client("ann", ["hello\n", "how are you\n"]),
             client("bob", ["a\n", "b\n", "c\n"], at=10),
             client("cy", ["late\n"], at=50_000, close="shutdown")]
    m = run(tmp_path, ECHO_SERVER, peers)
    assert m.state == "idle", (m.fault, m.kernel.peer_report())
    assert m.kernel.peer_report() == []
    assert [bytes(p.received) for p in m.kernel.peers] == [b"hello\nhow are you\n", b"a\nb\nc\n", b"late\n"]
    assert m.kernel.time_ns >= 1_700_000_000 * 10**9 + 50_000_000   # time jumped to cy


def test_a_client_waits_for_an_answer_that_never_comes(tmp_path):
    src = ECHO_SERVER.replace("    mov rdx, rax                ; write it back (small: it fits)\n"
                              "    mov eax, 1\n    mov rdi, rbx\n    lea rsi, [buf]\n    syscall\n", "")
    m = run(tmp_path, src, [client("ann", ["hello\n"])])
    assert m.state == "idle"
    report = m.kernel.peer_report()
    assert len(report) == 1 and "ann: waited for b'hello\\n'" in report[0] and "gave up" in report[0]


def test_nobody_listening(tmp_path):
    # The program waits forever on its own pipe; the client gives up after 100 tries.
    src = """global _start
_start:
    mov eax, 22
    lea rdi, [rsp - 16]
    syscall
    xor eax, eax
    mov edi, [rsp - 16]
    lea rsi, [rsp - 32]
    mov edx, 1
    syscall
"""
    m = run(tmp_path, src, [client("ann", ["x"])])
    assert m.state == "idle"
    assert m.kernel.peer_report() == ["ann: couldn't connect to 7000: nobody is listening there"]


TIMER = r"""
; three ticks of a 250 ms periodic timerfd, then the time it took
global _start
section .text
_start:
    mov eax, 228                ; clock_gettime(CLOCK_MONOTONIC, &t0)
    mov edi, 1
    lea rsi, [t0]
    syscall
    mov eax, 283                ; timerfd_create(CLOCK_MONOTONIC, 0)
    mov edi, 1
    xor esi, esi
    syscall
    mov r12, rax
    mov eax, 286                ; timerfd_settime(fd, 0, &spec, 0)
    mov rdi, r12
    xor esi, esi
    lea rdx, [spec]
    xor r10d, r10d
    syscall
    xor r13d, r13d              ; total expirations
.tick:
    xor eax, eax
    mov rdi, r12
    lea rsi, [count]
    mov edx, 8
    syscall
    add r13, [count]
    cmp r13, 3
    jb .tick
    mov eax, 228
    mov edi, 1
    lea rsi, [t1]
    syscall
    mov rax, [t1]               ; elapsed ms = (t1 - t0) in ms
    sub rax, [t0]
    imul rax, rax, 1000
    mov rcx, [t1 + 8]
    sub rcx, [t0 + 8]
    mov rdi, rcx
    mov rcx, 1000000
    push rax
    mov rax, rdi
    cqo
    idiv rcx
    pop rdi
    add rdi, rax
    mov eax, 60                 ; exit(elapsed ms / 10)
    push rdi
    pop rax
    xor edx, edx
    mov ecx, 10
    div rcx
    mov rdi, rax
    mov eax, 60
    syscall
section .data
spec: dq 0, 250_000_000, 0, 250_000_000     ; interval 250 ms, first in 250 ms
section .bss
t0: resq 2
t1: resq 2
count: resq 1
"""


def test_timerfd_and_virtual_time(tmp_path):
    m = run(tmp_path, TIMER, [])
    assert (m.state, m.exit_code) == ("exited", 75), m.fault   # 750 ms


NONBLOCK_PIPE = r"""
global _start
section .text
_start:
    mov eax, 293                ; pipe2(fds, O_NONBLOCK)
    lea rdi, [fds]
    mov esi, 0o4000
    syscall
    xor eax, eax                ; read from the empty pipe: -EAGAIN, not a hang
    mov edi, [fds]
    lea rsi, [buf]
    mov edx, 1
    syscall
    neg rax
    mov rdi, rax
    mov eax, 60
    syscall
section .bss
fds: resd 2
buf: resb 1
"""


def test_nonblocking_pipe(tmp_path):
    m = run(tmp_path, NONBLOCK_PIPE, [])
    assert (m.state, m.exit_code) == ("exited", 11)


@pytest.mark.parametrize("quantum", [1, 13])
def test_echo_server_with_short_reads(tmp_path, quantum):
    peers = [client(f"c{i}", [f"line {j} of {i}\n" for j in range(3)], at=i * 7) for i in range(4)]
    m = run(tmp_path, ECHO_SERVER, peers, inject={"short_reads": True, "quantum": quantum})
    assert m.state == "idle" and m.kernel.peer_report() == []


from .conftest import needs_native  # noqa: E402


@needs_native
def test_echo_server_matches_native(tmp_path):
    """The same server on the real kernel, with real TCP clients."""
    import socket
    import subprocess
    import time
    with socket.socket() as s:                     # a free port
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    src = ECHO_SERVER.replace("7000 >> 8, 7000 & 0xFF", f"{port >> 8}, {port & 0xFF}")
    (tmp_path / "n.asm").write_text(src)
    b = build(tmp_path / "n.asm", tmp_path / "nb", "program")
    server = subprocess.Popen([str(b.elf)])
    try:
        clients = []
        for _ in range(50):
            try:
                clients = [socket.create_connection(("127.0.0.1", port), timeout=5) for _ in range(3)]
                break
            except ConnectionRefusedError:
                time.sleep(0.05)
        for i, c in enumerate(clients):
            c.sendall(f"hello {i}\n".encode())
        for i, c in enumerate(reversed(clients)):
            want = f"hello {2 - i}\n".encode()
            got = b""
            while len(got) < len(want):
                got += c.recv(100)
            assert got == want
        for c in clients:
            c.close()
        assert server.poll() is None              # still serving
    finally:
        server.kill()


def test_pipe_peers_and_nonblocking_polling(tmp_path):
    """Two pipes fed over time; the program polls both with O_NONBLOCK and a 1 ms sleep."""
    src = r"""
global _start
section .text
_start:
    mov eax, 72                 ; fcntl(3, F_SETFL, O_NONBLOCK), same for 4
    mov edi, 3
    mov esi, 4
    mov edx, 0o4000
    syscall
    mov eax, 72
    mov edi, 4
    mov esi, 4
    mov edx, 0o4000
    syscall
    xor r12d, r12d              ; which fds hit EOF (bit 0: 3, bit 1: 4)
.poll:
    mov ebx, 3
    call drain
    mov ebx, 4
    call drain
    cmp r12d, 3
    je .done
    mov eax, 35                 ; nanosleep(1 ms)
    lea rdi, [ms]
    xor esi, esi
    syscall
    jmp .poll
.done:
    mov eax, 60
    xor edi, edi
    syscall
drain:                          ; copy whatever fd ebx has to stdout
    xor eax, eax
    mov edi, ebx
    lea rsi, [buf]
    mov edx, 256
    syscall
    cmp rax, -11
    je .none
    test rax, rax
    jle .eof
    mov rdx, rax
    mov eax, 1
    mov edi, 1
    lea rsi, [buf]
    syscall
    jmp drain
.eof:
    lea ecx, [rbx - 3]
    mov eax, 1
    shl eax, cl
    or r12d, eax
.none:
    ret
section .data
ms: dq 0, 1000000
section .bss
buf: resb 256
"""
    peers = [{"pipe": 3, "steps": [{"send": "A1 "}, {"sleep": 30_000}, {"send": "A2 "}]},
             {"pipe": 4, "steps": [{"sleep": 10_000}, {"send": "B1 "}, {"sleep": 10_000},
                                   {"send": "B2 "}, {"sleep": 20_000}, {"send": "B3 "}]}]
    m = run(tmp_path, src, peers)
    assert m.state == "exited", m.fault
    assert bytes(m.stdout) == b"A1 B1 B2 A2 B3 "
