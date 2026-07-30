from sqlalchemy import inspect, text

from app.database import Base, engine
from app import models  # noqa: F401


def ensure_sqlite_schema_additions() -> None:
    """Apply small additive SQLite updates for existing local dev databases."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "sale_items" in table_names:
            sale_item_columns = {column["name"] for column in inspector.get_columns("sale_items")}
            if "product_id" not in sale_item_columns:
                connection.execute(text("ALTER TABLE sale_items ADD COLUMN product_id INTEGER REFERENCES products(id)"))
            if "incremental_mrr" not in sale_item_columns:
                connection.execute(text("ALTER TABLE sale_items ADD COLUMN incremental_mrr NUMERIC(12, 2)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_sale_items_product_id ON sale_items (product_id)"))

        source_tables = ("companies", "locations", "contacts")
        for table_name in source_tables:
            if table_name not in table_names:
                continue
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in (
                ("source_system", "VARCHAR(80)"),
                ("external_id", "VARCHAR(160)"),
                ("last_imported_at", "DATETIME"),
            ):
                if column_name not in columns:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
            if table_name == "companies" and "lead_source" not in columns:
                connection.execute(text("ALTER TABLE companies ADD COLUMN lead_source VARCHAR(120)"))

        if "companies" in table_names:
            company_columns = {column["name"] for column in inspector.get_columns("companies")}
            for column_name, column_type in (
                ("is_active", "BOOLEAN DEFAULT 1 NOT NULL"),
                ("lead_source_legacy", "VARCHAR(120)"),
                ("referral_partner_id", "INTEGER REFERENCES referral_partners(id)"),
                ("referred_at", "DATETIME"),
            ):
                if column_name not in company_columns:
                    connection.execute(text(f"ALTER TABLE companies ADD COLUMN {column_name} {column_type}"))
            connection.execute(
                text(
                    "UPDATE companies SET lead_source = 'AE_FOUND' "
                    "WHERE lower(trim(lead_source)) IN ('ae found', 'ae_found', 'aefound')"
                )
            )
            connection.execute(
                text(
                    "UPDATE companies SET lead_source = 'REFERRAL' "
                    "WHERE lower(trim(lead_source)) = 'referral'"
                )
            )
            connection.execute(
                text(
                    "UPDATE companies SET lead_source_legacy = lead_source, lead_source = NULL "
                    "WHERE lead_source IS NOT NULL "
                    "AND lead_source NOT IN ('AE_FOUND', 'REFERRAL') "
                    "AND (lead_source_legacy IS NULL OR lead_source_legacy = '')"
                )
            )

        for table_name in ("locations", "contacts"):
            if table_name not in table_names:
                continue
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in (
                ("is_active", "BOOLEAN DEFAULT 1 NOT NULL"),
                ("inactive_reason", "VARCHAR(120)"),
                ("inactive_at", "DATETIME"),
            ):
                if column_name not in columns:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))

        if "activities" in table_names:
            activity_columns = {column["name"] for column in inspector.get_columns("activities")}
            if "referral_partner_id" not in activity_columns:
                connection.execute(text("ALTER TABLE activities ADD COLUMN referral_partner_id INTEGER REFERENCES referral_partners(id)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_activities_referral_partner_id ON activities (referral_partner_id)"))

        if "commission_tiers" in table_names:
            tier_columns = {column["name"] for column in inspector.get_columns("commission_tiers")}
            if "display_name" not in tier_columns:
                connection.execute(text("ALTER TABLE commission_tiers ADD COLUMN display_name VARCHAR(80)"))
            if "display_icon" not in tier_columns:
                connection.execute(text("ALTER TABLE commission_tiers ADD COLUMN display_icon VARCHAR(16)"))

        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_source_external_id "
                "ON companies (source_system, external_id) "
                "WHERE source_system IS NOT NULL AND external_id IS NOT NULL"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_locations_source_external_id "
                "ON locations (source_system, external_id) "
                "WHERE source_system IS NOT NULL AND external_id IS NOT NULL"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_contacts_source_external_id "
                "ON contacts (source_system, external_id) "
                "WHERE source_system IS NOT NULL AND external_id IS NOT NULL"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_referral_partners_source_external_id "
                "ON referral_partners (source_system, external_id) "
                "WHERE source_system IS NOT NULL AND external_id IS NOT NULL"
            )
        )


def init_db() -> list[str]:
    """Create all registered SQLAlchemy tables and return their names."""
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema_additions()
    return inspect(engine).get_table_names()


if __name__ == "__main__":
    for table_name in init_db():
        print(table_name)
