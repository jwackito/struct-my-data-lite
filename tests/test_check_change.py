from pathlib import Path

import pytest

from scripts.check_change import change_name_from_branch, resolve_change, touched


@pytest.mark.parametrize(
    ("branch", "expected"),
    [
        ("change/adopt-openspec-workflow", "adopt-openspec-workflow"),
        ("change/docs-verify-lightweight", "docs-verify-lightweight"),
        ("change/a1", "a1"),
    ],
)
def test_change_name_from_branch_accepts_kebab(branch, expected):
    assert change_name_from_branch(branch) == expected


@pytest.mark.parametrize(
    "branch",
    [
        "main",
        "feat/42-per-user-concurrency",
        "chore/13-openspec-guards",
        "change/",
        "change/Bad",
        "change/two--hyphens",
        "change/-leading",
        "change/trailing-",
        "change/under_score",
    ],
)
def test_change_name_from_branch_rejects_other_forms(branch):
    assert change_name_from_branch(branch) is None


def test_resolve_change_prefers_active(tmp_path):
    changes = tmp_path / "changes"
    (changes / "add-thing").mkdir(parents=True)

    assert resolve_change("add-thing", changes, changes / "archive") == (
        changes / "add-thing",
        False,
    )


def test_resolve_change_finds_archived(tmp_path):
    changes = tmp_path / "changes"
    archived = changes / "archive" / "2026-10-28-add-thing"
    archived.mkdir(parents=True)

    assert resolve_change("add-thing", changes, changes / "archive") == (
        archived,
        True,
    )


def test_resolve_change_rejects_ambiguous_archive(tmp_path):
    changes = tmp_path / "changes"
    (changes / "archive" / "2026-10-01-add-thing").mkdir(parents=True)
    (changes / "archive" / "2026-10-28-add-thing").mkdir(parents=True)

    assert resolve_change("add-thing", changes, changes / "archive") is None


def test_resolve_change_missing(tmp_path):
    changes = tmp_path / "changes"
    changes.mkdir()

    assert resolve_change("add-thing", changes, changes / "archive") is None


def test_touched_accepts_paths_inside_change(tmp_path):
    change = tmp_path / "openspec" / "changes" / "add-thing"
    change.mkdir(parents=True)
    paths = {
        "openspec/changes/add-thing/proposal.md",
        "openspec/changes/add-thing/specs/auth/spec.md",
    }

    assert touched(paths, change, tmp_path) is True


def test_touched_rejects_other_paths(tmp_path):
    change = tmp_path / "openspec" / "changes" / "add-thing"
    change.mkdir(parents=True)
    paths = {
        "openspec/changes/other-change/proposal.md",
        "app/main.py",
    }

    assert touched(paths, change, tmp_path) is False


def test_touched_rejects_prefix_collision(tmp_path):
    change = tmp_path / "openspec" / "changes" / "add-thing"
    change.mkdir(parents=True)
    paths = {"openspec/changes/add-thing-else/proposal.md"}

    assert touched(paths, change, tmp_path) is False
