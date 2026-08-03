"""Shared test helpers."""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_build_views():
    return _load_script("build_views")


def load_smoke_checks() -> dict:
    return _load_script("smoke_test").CHECKS
