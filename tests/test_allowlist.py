import textwrap
from pathlib import Path

import pytest

from app.allowlist import is_allowed, load_allowlist


def test_load_from_env_only() -> None:
    result = load_allowlist("Alice@Example.com, bob@example.com", "")
    assert result == {"alice@example.com", "bob@example.com"}


def test_load_from_file(tmp_path: Path) -> None:
    f = tmp_path / "senders.txt"
    f.write_text("carol@example.com\n# comment\ndave@example.com\n")
    result = load_allowlist("", str(f))
    assert result == {"carol@example.com", "dave@example.com"}


def test_merge_env_and_file(tmp_path: Path) -> None:
    f = tmp_path / "senders.txt"
    f.write_text("carol@example.com\n")
    result = load_allowlist("alice@example.com", str(f))
    assert result == {"alice@example.com", "carol@example.com"}


def test_missing_file_returns_env_only(tmp_path: Path) -> None:
    result = load_allowlist("alice@example.com", str(tmp_path / "nonexistent.txt"))
    assert result == {"alice@example.com"}


def test_empty_env_and_no_file() -> None:
    result = load_allowlist("", "")
    assert result == set()


def test_is_allowed_case_insensitive() -> None:
    allowlist = {"alice@example.com"}
    assert is_allowed("Alice@Example.COM", allowlist)
    assert not is_allowed("bob@example.com", allowlist)


def test_comments_and_blank_lines_skipped(tmp_path: Path) -> None:
    content = textwrap.dedent("""\
        # admin list
        alice@example.com

        # another section
        bob@example.com
        # end
    """)
    f = tmp_path / "senders.txt"
    f.write_text(content)
    result = load_allowlist("", str(f))
    assert result == {"alice@example.com", "bob@example.com"}
