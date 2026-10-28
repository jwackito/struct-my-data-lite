#!/usr/bin/env python3
"""Validate that a pull request carries its OpenSpec change."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHANGES_DIR = REPO_ROOT / "openspec" / "changes"
ARCHIVE_DIR = CHANGES_DIR / "archive"
DEFAULT_OPENSPEC_VERSION = "1.14.3"


def change_name_from_branch(branch: str) -> str | None:
    """Return the change name for change/<name>, or None for any other branch."""
    prefix = "change/"
    if not branch.startswith(prefix):
        return None
    name = branch[len(prefix):]
    if not name or name.startswith("-") or name.endswith("-") or "--" in name:
        return None
    if any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in name):
        return None
    return name


def resolve_change(
    name: str,
    changes_dir: Path = CHANGES_DIR,
    archive_dir: Path = ARCHIVE_DIR,
) -> tuple[Path, bool] | None:
    """Return (path, archived) for an active or archived change, or None."""
    active = changes_dir / name
    if active.is_dir():
        return active, False
    matches = sorted(p for p in archive_dir.glob(f"*-{name}") if p.is_dir())
    if len(matches) == 1:
        return matches[0], True
    return None


def touched(paths: set[str], change_path: Path, repo_root: Path = REPO_ROOT) -> bool:
    """Whether any changed path lives inside the change directory."""
    prefix = change_path.relative_to(repo_root).as_posix().rstrip("/") + "/"
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for path in paths)


def changed_files(base: str, head: str, repo_root: Path = REPO_ROOT) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", f"{base}...{head}"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def openspec_command() -> list[str]:
    binary = os.environ.get("OPENSPEC_BIN") or shutil.which("openspec")
    if binary:
        return [binary]
    version = os.environ.get("OPENSPEC_VERSION", DEFAULT_OPENSPEC_VERSION)
    return ["npx", "-y", f"@fission-ai/openspec@{version}"]


def validate(change: Path, archived: bool) -> None:
    cmd = openspec_command()
    if archived:
        subprocess.run([*cmd, "validate", "--archived"], cwd=REPO_ROOT, check=True)
    else:
        subprocess.run(
            [*cmd, "validate", change.name, "--strict"],
            cwd=REPO_ROOT,
            check=True,
        )
    subprocess.run(
        [*cmd, "validate", "--specs", "--strict"],
        cwd=REPO_ROOT,
        check=True,
    )


def current_branch(repo_root: Path = REPO_ROOT) -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    branch = os.environ.get("GITHUB_HEAD_REF") or current_branch()
    name = change_name_from_branch(branch)
    if name is None:
        print(f"::error::Branch '{branch}' must be change/<change-name>.", file=sys.stderr)
        return 1

    resolved = resolve_change(name)
    if resolved is None:
        print(
            "::error::No OpenSpec change at "
            f"openspec/changes/{name}/ or openspec/changes/archive/*-{name}/.",
            file=sys.stderr,
        )
        return 1

    change, archived = resolved
    base = os.environ.get("BASE_SHA")
    head = os.environ.get("HEAD_SHA") or "HEAD"
    if base:
        paths = changed_files(base, head)
        if not touched(paths, change):
            print(
                f"::error::The PR does not touch {change.relative_to(REPO_ROOT)}.",
                file=sys.stderr,
            )
            return 1

    validate(change, archived)
    state = "archived" if archived else "active"
    print(f"OpenSpec change '{name}' validated ({state}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
