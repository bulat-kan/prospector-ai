import sys
from collections.abc import Callable
from pathlib import Path

from app.database import DATA_DIR, DATABASE_PATH, engine
from app.init_db import init_db
from app.seed_demo import main as seed_main


def is_safe_development_database_path(database_path: Path) -> bool:
    resolved_path = database_path.resolve()
    resolved_data_dir = DATA_DIR.resolve()
    return (
        resolved_path.name == "prospector_ai.db"
        and resolved_path.parent == resolved_data_dir
        and resolved_data_dir.parent == Path(__file__).resolve().parent.parent
    )


def reset_development_database(
    *,
    database_path: Path = DATABASE_PATH,
    confirmed: bool = False,
    init_callable: Callable[[], object] = init_db,
    seed_callable: Callable[[], object] = seed_main,
    dispose_callable: Callable[[], object] = engine.dispose,
    safety_checker: Callable[[Path], bool] = is_safe_development_database_path,
) -> int:
    print("Development database:")
    print(f" {database_path.resolve()}")

    if not confirmed:
        print("This command deletes and recreates the local development SQLite database.")
        print("Rerun with --yes to continue.")
        return 2

    if not safety_checker(database_path):
        print("Refusing to reset an unsafe or unknown database path.")
        return 3

    try:
        dispose_callable()
        if database_path.exists():
            print("Removing development database...")
            database_path.unlink()
        else:
            print("No existing development database found.")

        print("Initializing schema...")
        init_callable()

        print("Seeding demo data...")
        seed_callable()

        print("Development database reset completed successfully.")
        return 0
    except Exception as exc:
        print(f"Development database reset failed: {exc}")
        return 1


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    return reset_development_database(confirmed="--yes" in args)


if __name__ == "__main__":
    raise SystemExit(main())
