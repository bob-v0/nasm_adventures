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


def test_arc_one_is_complete():
    assert sorted(LEVELS) == [n for n in range(171, 185) if n not in (172, 173)] or sorted(LEVELS) == list(range(171, 185))


@pytest.mark.parametrize("ring", sorted(LEVELS, reverse=True))
def test_level(ring, tmp_path):
    assert check_level(LEVELS[ring], CTX, tmp_path) == []


@pytest.mark.parametrize("ring", sorted(r for r, lv in LEVELS.items() if lv.mode == "program"))
@needs_native
def test_emulator_matches_native(ring, tmp_path):
    lv = LEVELS[ring]
    b = build_copy(lv, lv.reference, tmp_path)
    for test in lv.all_tests(CTX)[:5]:
        if test.mem:
            continue  # memory pokes only exist in the emulator
        result, m = run_test(lv, b, test)
        native = subprocess.run([str(b.elf)], input=test.stdin, capture_output=True, timeout=5)
        assert bytes(m.stdout) == native.stdout
        assert bytes(m.stderr) == native.stderr
        assert m.exit_code == native.returncode
