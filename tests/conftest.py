import os
import platform
import shutil

import pytest

NATIVE = platform.system() == "Linux" and platform.machine() in ("x86_64", "AMD64")


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("RING_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.delenv("RING_DEV", raising=False)


needs_native = pytest.mark.skipif(not NATIVE or not shutil.which("nasm"),
                                  reason="needs x86-64 Linux with nasm")
