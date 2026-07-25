from sqlalchemy import inspect, text

from app.database import Base, engine
from app import models  # noqa: F401


def ensure_sqlite_schema_additions() -> None:
    """Apply small additive SQLite updates for existing local dev databases."""
    inspector = inspect(engine)
    if "sale_items" not in inspector.get_table_names():
        return

    sale_item_columns = {column["name"] for column in inspector.get_columns("sale_items")}
    with engine.begin() as connection:
        if "product_id" not in sale_item_columns:
            connection.execute(text("ALTER TABLE sale_items ADD COLUMN product_id INTEGER REFERENCES products(id)"))
        if "incremental_mrr" not in sale_item_columns:
            connection.execute(text("ALTER TABLE sale_items ADD COLUMN incremental_mrr NUMERIC(12, 2)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_sale_items_product_id ON sale_items (product_id)"))


def init_db() -> list[str]:
    """Create all registered SQLAlchemy tables and return their names."""
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema_additions()
    return inspect(engine).get_table_names()


if __name__ == "__main__":
    for table_name in init_db():
        print(table_name)
