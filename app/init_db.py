from sqlalchemy import inspect

from app.database import Base, engine
from app import models  # noqa: F401


def init_db() -> list[str]:
    """Create all registered SQLAlchemy tables and return their names."""
    Base.metadata.create_all(bind=engine)
    return inspect(engine).get_table_names()


if __name__ == "__main__":
    for table_name in init_db():
        print(table_name)
