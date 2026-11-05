from __future__ import annotations

from pathlib import Path

import pytest

from crawler_core.paths import (
    find_project_root,
    resolve_path_argument,
    resolve_project_path,
    timestamped_output_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_finds_current_project_from_nested_script() -> None:
    assert find_project_root(__file__) == PROJECT_ROOT


@pytest.mark.parametrize("prefix", ["", "./", "important_people/"])
def test_resolves_project_relative_path_with_forward_slashes(prefix: str) -> None:
    resolved = resolve_project_path(
        prefix + "workspace/module/README_人物抽取筛选词表说明.md",
        anchor=__file__,
        must_exist=True,
    )
    assert resolved == (
        PROJECT_ROOT / "workspace" / "module" / "README_人物抽取筛选词表说明.md"
    )


@pytest.mark.parametrize("value", [".", "./", "important_people"])
def test_resolves_project_root(value: str) -> None:
    assert resolve_project_path(value, anchor=__file__) == PROJECT_ROOT


def test_resolves_from_another_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert (
        resolve_project_path("workspace", anchor=__file__, must_exist=True)
        == PROJECT_ROOT / "workspace"
    )
    assert resolve_path_argument("outputs", anchor=__file__) == PROJECT_ROOT / "outputs"


def test_finds_renamed_project(tmp_path: Path) -> None:
    renamed_root = tmp_path / "项目副本"
    (renamed_root / "crawler_core").mkdir(parents=True)
    (renamed_root / "workspace" / "source_data").mkdir(parents=True)
    (renamed_root / "AGENTS.md").write_text("project", encoding="utf-8")
    anchor = renamed_root / "workspace" / "nested" / "tool.py"
    assert find_project_root(anchor) == renamed_root
    assert (
        resolve_project_path("workspace/source_data", anchor=anchor, must_exist=True)
        == renamed_root / "workspace" / "source_data"
    )
    assert (
        resolve_project_path("important_people/workspace", anchor=anchor)
        == renamed_root / "workspace"
    )


def test_reports_missing_project_markers() -> None:
    with pytest.raises(FileNotFoundError):
        find_project_root(PROJECT_ROOT.parent)


def test_resolves_windows_separators() -> None:
    assert (
        resolve_project_path(r"workspace\source_data", anchor=__file__)
        == PROJECT_ROOT / "workspace" / "source_data"
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "../outside.txt",
        "workspace/../../outside.txt",
        "important_people/../outside.txt",
        "D:/Desktop/important_people/workspace/module/file.py",
        "C:\\project\\file.py",
        "C:relative.txt",
        "/outside.txt",
        r"\outside.txt",
        r"\\server\share\file.txt",
    ],
)
def test_rejects_absolute_or_unsafe_paths(value: str) -> None:
    with pytest.raises(ValueError):
        resolve_project_path(value, anchor=__file__)


def test_reports_missing_required_path() -> None:
    with pytest.raises(FileNotFoundError):
        resolve_project_path(
            "workspace/module/not-present.txt",
            anchor=__file__,
            must_exist=True,
        )


def test_path_argument_keeps_programmatic_path_compatibility(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("ok", encoding="utf-8")
    assert resolve_path_argument(target, anchor=__file__, must_exist=True) == target.resolve()


def test_timestamped_output_path_adds_one_stable_suffix() -> None:
    timestamp = "20261020_012345"
    source = Path("workspace/log/sample.log")
    timestamped = timestamped_output_path(source, timestamp)
    assert timestamped == Path("workspace/log/sample_20261020_012345.log")
    assert timestamped_output_path(timestamped, timestamp) == timestamped


def test_timestamped_output_path_rejects_invalid_timestamp() -> None:
    with pytest.raises(ValueError):
        timestamped_output_path(Path("sample.txt"), "2026-10-20")
