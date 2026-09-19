"""Phase 0 smoke test — verifies the project imports and tooling works."""

from __future__ import annotations

from pathlib import Path


def test_project_root_importable() -> None:
    """The project root must be on sys.path for `import core` to work."""
    import core  # noqa: F401
    import utils  # noqa: F401


def test_pyproject_exists() -> None:
    """pyproject.toml must exist for tooling to work."""
    assert (Path(__file__).resolve().parent.parent / "pyproject.toml").exists()


def test_makefile_exists() -> None:
    """Makefile must exist for `make` commands to work."""
    assert (Path(__file__).resolve().parent.parent / "Makefile").exists()
