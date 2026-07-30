from pathlib import Path

import pytest

from app import seed_demo
from app.reset_demo_data import is_safe_development_database_path, main, reset_development_database


def test_seed_demo_exposes_callable_main() -> None:
    assert callable(seed_demo.main)


def test_reset_refuses_without_yes(tmp_path, capsys) -> None:
    db_path = tmp_path / "prospector_ai.db"

    result = reset_development_database(
        database_path=db_path,
        confirmed=False,
        safety_checker=lambda path: True,
    )

    assert result == 2
    assert "Rerun with --yes" in capsys.readouterr().out


def test_reset_rejects_unsafe_database_path(tmp_path, capsys) -> None:
    db_path = tmp_path / "production.db"

    result = reset_development_database(database_path=db_path, confirmed=True)

    assert result == 3
    assert "unsafe" in capsys.readouterr().out


def test_reset_removes_existing_database_and_calls_init_and_seed(tmp_path) -> None:
    db_path = tmp_path / "prospector_ai.db"
    db_path.write_text("old data")
    calls: list[str] = []

    result = reset_development_database(
        database_path=db_path,
        confirmed=True,
        init_callable=lambda: calls.append("init") or db_path.write_text("schema"),
        seed_callable=lambda: calls.append("seed"),
        dispose_callable=lambda: calls.append("dispose"),
        safety_checker=lambda path: path == db_path,
    )

    assert result == 0
    assert calls == ["dispose", "init", "seed"]
    assert db_path.read_text() == "schema"


def test_reset_recreates_schema_when_database_missing(tmp_path) -> None:
    db_path = tmp_path / "prospector_ai.db"

    result = reset_development_database(
        database_path=db_path,
        confirmed=True,
        init_callable=lambda: db_path.write_text("schema"),
        seed_callable=lambda: None,
        dispose_callable=lambda: None,
        safety_checker=lambda path: True,
    )

    assert result == 0
    assert db_path.exists()


def test_reset_returns_nonzero_on_initialization_failure(tmp_path, capsys) -> None:
    db_path = tmp_path / "prospector_ai.db"

    def fail_init() -> None:
        raise RuntimeError("init failed")

    result = reset_development_database(
        database_path=db_path,
        confirmed=True,
        init_callable=fail_init,
        seed_callable=lambda: None,
        dispose_callable=lambda: None,
        safety_checker=lambda path: True,
    )

    assert result == 1
    assert "init failed" in capsys.readouterr().out


def test_reset_returns_nonzero_on_seeding_failure(tmp_path, capsys) -> None:
    db_path = tmp_path / "prospector_ai.db"

    def fail_seed() -> None:
        raise RuntimeError("seed failed")

    result = reset_development_database(
        database_path=db_path,
        confirmed=True,
        init_callable=lambda: None,
        seed_callable=fail_seed,
        dispose_callable=lambda: None,
        safety_checker=lambda path: True,
    )

    assert result == 1
    assert "seed failed" in capsys.readouterr().out


def test_main_parses_yes(monkeypatch) -> None:
    called = {}

    def fake_reset(*, confirmed: bool) -> int:
        called["confirmed"] = confirmed
        return 0

    monkeypatch.setattr("app.reset_demo_data.reset_development_database", fake_reset)

    assert main(["--yes"]) == 0
    assert called["confirmed"] is True


def test_default_development_database_path_is_safe() -> None:
    from app.database import DATABASE_PATH

    assert is_safe_development_database_path(DATABASE_PATH) is True


def test_arbitrary_database_path_is_not_safe(tmp_path) -> None:
    assert is_safe_development_database_path(tmp_path / "prospector_ai.db") is False
