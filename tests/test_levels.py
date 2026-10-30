"""Every level's reference passes and its starter fails; program-mode references
behave identically in the emulator and on the real CPU."""

import subprocess

import pytest

from ring.authoring import build_copy, check_level
from ring.checks import run_test
from ring.level import Context, all_levels

from .conftest import needs_native

LEVELS = all_levels()
CTX = Context(seed=1234)


def test_levels_are_contiguous_from_184():
    assert sorted(LEVELS) == list(range(min(LEVELS), 185))


@pytest.mark.parametrize("ring", sorted(LEVELS, reverse=True))
def test_level(ring, tmp_path):
    assert check_level(LEVELS[ring], CTX, tmp_path) == []


@pytest.mark.parametrize("ring", sorted(r for r, lv in LEVELS.items() if lv.mode == "program"
                                         and not (lv.path / "helpers.asm").exists()))
@needs_native
def test_emulator_matches_native(ring, tmp_path):
    lv = LEVELS[ring]
    b = build_copy(lv, lv.reference, tmp_path)
    for test in lv.all_tests(CTX)[:8]:
        if test.mem or test.files or test.inject or test.expect.get("check"):
            continue  # memory pokes, virtual files and injected faults only exist in the emulator
        result, m = run_test(lv, b, test)
        argv = test.argv or ["./solution"]
        native = subprocess.run(argv, executable=str(b.elf), input=test.stdin, capture_output=True,
                                timeout=5, env=test.env, cwd=b.elf.parent)
        assert bytes(m.stdout) == native.stdout
        assert bytes(m.stderr) == native.stderr
        assert m.exit_code == native.returncode


def test_flags_quiz_answers_match_the_cpu(tmp_path):
    """Level 169's expected answers must be what the CPU really does."""
    import tomllib

    from ring.build import build
    from ring.emu import FLAG_BITS, Machine

    lv = LEVELS[169]
    ops = ["mov al, 0xFF\nadd al, 1", "mov al, 0x7F\nadd al, 1", "mov al, 0x80\nsub al, 1",
           "mov al, 0\nsub al, 1", "mov eax, 5\nsub eax, 5", "mov rax, -1\nadd rax, -1",
           "mov al, 0x80\nadd al, 0x80", "mov al, 0x40\nadd al, 0x40"]
    want = bytes.fromhex(tomllib.loads((lv.path / "level.toml").read_text())
                         ["tests"][0]["expect"]["mem"][0]["hex"].replace(" ", ""))
    bits = dict(FLAG_BITS)
    for i, op in enumerate(ops):
        src = tmp_path / f"op{i}.asm"
        src.write_text(op + "\n")
        m = Machine(build(src, tmp_path / f"b{i}", "fragment"))
        m.run()
        got = bytes(m.reg("rflags") >> bits[f] & 1 for f in ("CF", "ZF", "SF", "OF"))
        assert got == want[4 * i:4 * i + 4], f"operation {i + 1}: {op!r}"
