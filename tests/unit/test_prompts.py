"""Unit tests for LLM prompts (language detection, prompt keys, overrides, template building)."""

from __future__ import annotations

from pathlib import Path

import pytest

from paranoid.llm.prompts import (
    detect_directory_language,
    detect_language,
    description_length_for_content,
    directory_summary_prompt,
    file_summary_prompt,
    get_builtin_template,
    get_prompt_keys,
    load_overrides_from_project,
    set_prompt_overrides,
)
from paranoid.storage.models import Summary


def test_detect_language_python() -> None:
    assert detect_language("/a/b/foo.py") == "python"
    assert detect_language("script.PY") == "python"
    assert detect_language(Path("/x/bar.pyi")) == "python"


def test_detect_language_js_ts() -> None:
    assert detect_language("a.js") == "javascript"
    assert detect_language("b.ts") == "typescript"
    assert detect_language("c.jsx") == "javascript-react"
    assert detect_language("d.tsx") == "typescript-react"


def test_detect_language_other() -> None:
    assert detect_language("e.go") == "go"
    assert detect_language("f.rs") == "rust"
    assert detect_language("g.md") == "markdown"
    assert detect_language("h.txt") == "text"


def test_detect_language_unknown() -> None:
    assert detect_language("noext") == "unknown"
    assert detect_language(".hidden") == "unknown"
    assert detect_language("file.xyz") == "unknown"


def test_detect_directory_language_empty() -> None:
    assert detect_directory_language([]) == "unknown"


def test_detect_directory_language_only_dirs() -> None:
    children = [
        Summary(path="/p/dir1", type="directory", hash="h1", description="d", language="python"),
    ]
    assert detect_directory_language(children) == "unknown"


def test_detect_directory_language_files() -> None:
    children = [
        Summary(path="/p/a.py", type="file", hash="h1", description="d", language="python"),
        Summary(path="/p/b.py", type="file", hash="h2", description="d", language="python"),
        Summary(path="/p/c.js", type="file", hash="h3", description="d", language="javascript"),
    ]
    assert detect_directory_language(children) == "python"


def test_detect_directory_language_tie_most_common() -> None:
    children = [
        Summary(path="/p/a.py", type="file", hash="h1", description="d", language="python"),
        Summary(path="/p/b.js", type="file", hash="h2", description="d", language="javascript"),
        Summary(path="/p/c.js", type="file", hash="h3", description="d", language="javascript"),
    ]
    assert detect_directory_language(children) == "javascript"


def test_detect_directory_language_none_treated_as_unknown() -> None:
    children = [
        Summary(path="/p/a.py", type="file", hash="h1", description="d", language=None),
    ]
    assert detect_directory_language(children) == "unknown"


def test_description_length_for_content() -> None:
    assert description_length_for_content("x" * 100) == "a few lines"
    assert description_length_for_content("x" * 5000) == "1-3 paragraphs"
    assert description_length_for_content("x" * 10000) == "1-3 paragraphs"
    assert description_length_for_content("x" * 20000) == "3-5 paragraphs"


def test_get_prompt_keys() -> None:
    keys = get_prompt_keys()
    assert ("python", "file") in keys
    assert ("python", "directory") in keys
    assert ("unknown", "file") in keys
    assert ("unknown", "directory") in keys
    assert all(k[1] in ("file", "directory") for k in keys)
    assert keys == sorted(keys, key=lambda x: (x[0], x[1]))


def test_get_builtin_template() -> None:
    t = get_builtin_template("python", "file")
    assert t is not None
    assert "Python" in t
    assert "{filename}" in t
    assert "{content}" in t
    t_dir = get_builtin_template("python", "directory")
    assert t_dir is not None
    assert "{dir_path}" in t_dir
    assert "{children}" in t_dir
    assert get_builtin_template("unknown", "file") is not None
    assert get_builtin_template("nosuchlang", "file") is not None  # falls back to unknown


def test_file_summary_prompt_uses_builtin() -> None:
    set_prompt_overrides(None)
    prompt = file_summary_prompt("/a/foo.py", "x = 1", language="python")
    assert "Python" in prompt
    assert "foo.py" in prompt
    assert "x = 1" in prompt
    assert "None" in prompt or "existing" in prompt.lower()


def test_file_summary_prompt_uses_override() -> None:
    set_prompt_overrides({"python:file": "CUSTOM PROMPT: {filename} | {content}"})
    try:
        prompt = file_summary_prompt("/a/bar.py", "hello", language="python")
        assert prompt.startswith("CUSTOM PROMPT:")
        assert "bar.py" in prompt
        assert "hello" in prompt
    finally:
        set_prompt_overrides(None)


def test_directory_summary_prompt_uses_override() -> None:
    set_prompt_overrides({"python:directory": "DIR CUSTOM: {dir_path} | {children}"})
    try:
        prompt = directory_summary_prompt("/a/b", "child1\nchild2", primary_language="python")
        assert "DIR CUSTOM" in prompt
        assert "/a/b" in prompt or "a/b" in prompt
        assert "child1" in prompt
    finally:
        set_prompt_overrides(None)


def test_load_overrides_from_project_missing(tmp_path: Path) -> None:
    assert load_overrides_from_project(tmp_path) == {}


def test_load_overrides_from_project_empty_file(tmp_path: Path) -> None:
    overrides_dir = tmp_path / ".paranoid-coder"
    overrides_dir.mkdir()
    (overrides_dir / "prompt_overrides.json").write_text("{}")
    assert load_overrides_from_project(tmp_path) == {}


def test_load_overrides_from_project_valid(tmp_path: Path) -> None:
    overrides_dir = tmp_path / ".paranoid-coder"
    overrides_dir.mkdir()
    (overrides_dir / "prompt_overrides.json").write_text(
        '{"python:file": "My custom prompt", "go:directory": "Go dir"}'
    )
    got = load_overrides_from_project(tmp_path)
    assert got == {"python:file": "My custom prompt", "go:directory": "Go dir"}


def test_load_overrides_from_project_invalid_json(tmp_path: Path) -> None:
    overrides_dir = tmp_path / ".paranoid-coder"
    overrides_dir.mkdir()
    (overrides_dir / "prompt_overrides.json").write_text("not json")
    assert load_overrides_from_project(tmp_path) == {}
