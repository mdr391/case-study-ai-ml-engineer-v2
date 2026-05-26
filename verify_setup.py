"""Basic scaffold verification without external installs."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Iterable


REQUIRED_PATHS: tuple[str, ...] = (
    "README.md",
    "app/main.py",
    ".env.example",
    "skills/scheduling-engine-service/SKILL.md",
    "skills/scheduling-engine-service/evals/evals.proposal.json",
)

REQUIRED_ROUTES: tuple[str, ...] = (
    "/health",
)

REQUIRED_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("anthropic", "anthropic"),
)


def _missing_paths(paths: Iterable[str]) -> list[str]:
    return [path for path in paths if not Path(path).exists()]


def _missing_dependencies(dependencies: Iterable[tuple[str, str]]) -> list[str]:
    missing: list[str] = []
    for module_name, package_name in dependencies:
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            missing.append(package_name)
    return missing


def main() -> int:
    missing_paths = _missing_paths(REQUIRED_PATHS)
    if missing_paths:
        print("Missing scaffold files:")
        for path in missing_paths:
            print(f"- {path}")
        return 1

    missing_dependencies = _missing_dependencies(REQUIRED_DEPENDENCIES)
    if missing_dependencies:
        print("Missing Python dependencies:")
        for package in missing_dependencies:
            print(f"- {package}")
        print("Install requirements and retry: pip install -r requirements.txt")
        return 1

    # Import checks ensure package layout is valid and executable.
    try:
        importlib.import_module("app.main")
    except ModuleNotFoundError as exc:
        print(f"Import check failed: missing module '{exc.name}'.")
        return 1
    except Exception as exc:  # Keep setup failures concise and traceback-free.
        print(f"Import check failed: {exc.__class__.__name__}: {exc}")
        return 1

    from app.main import app  # Imported after module checks.

    route_paths = {route.path for route in app.routes}
    missing_routes = [path for path in REQUIRED_ROUTES if path not in route_paths]
    if missing_routes:
        print("Missing required routes:")
        for path in missing_routes:
            print(f"- {path}")
        return 1

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or key in {"your-key-here", "your-key-will-be-pre-loaded"}:
        print("Scaffold verification passed.")
        print("Note: ANTHROPIC_API_KEY is not set (or still placeholder).")
    else:
        masked = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***set***"
        print("Scaffold verification passed.")
        print(f"ANTHROPIC_API_KEY detected ({masked}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
