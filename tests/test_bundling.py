"""Checks that keep the package safe to bundle into another package.

The package is copied as a subpackage into the ha-iotawatt Home Assistant
integration. That only works while every self-import is relative and the
only third-party dependency is httpx, which Home Assistant ships.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re
import sys
import tomllib

import pytest

ROOT = Path(__file__).parent.parent
PACKAGE = "iotawattpy_nosignal"
PACKAGE_FILES = sorted((ROOT / PACKAGE).glob("**/*.py"))
ALLOWED_DEPENDENCIES = {"httpx"}


def _absolute_imports(path: Path) -> list[str]:
    """Return the top-level module names a file imports absolutely."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module.split(".")[0])
    return modules


def test_package_files_found() -> None:
    assert PACKAGE_FILES


@pytest.mark.parametrize("path", PACKAGE_FILES, ids=lambda path: path.name)
def test_no_absolute_self_import(path: Path) -> None:
    """Self-imports must be relative so the package works under any name."""
    modules = _absolute_imports(path)
    assert PACKAGE not in modules
    assert "iotawattpy" not in modules


@pytest.mark.parametrize("path", PACKAGE_FILES, ids=lambda path: path.name)
def test_imports_only_stdlib_and_allowed(path: Path) -> None:
    """Only the standard library and declared dependencies are imported."""
    third_party = {
        module
        for module in _absolute_imports(path)
        if module not in sys.stdlib_module_names and module != "__future__"
    }
    assert third_party <= ALLOWED_DEPENDENCIES


def test_runtime_dependencies() -> None:
    """The only runtime dependency is httpx."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    names = {
        re.split(r"[\s<>=!~\[;]", requirement, maxsplit=1)[0].lower()
        for requirement in project.get("dependencies", [])
    }
    assert names == ALLOWED_DEPENDENCIES
    assert not project.get("optional-dependencies")
