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

        if "opportunities" in table_names:
            opportunity_column_info = inspector.get_columns("opportunities")
            opportunity_columns = {column["name"] for column in opportunity_column_info}
            for column_name, column_type in (
                ("notes", "TEXT"),
                ("is_active", "BOOLEAN DEFAULT 1 NOT NULL"),
                ("archived_at", "DATETIME"),
            ):
                if column_name not in opportunity_columns:
                    connection.execute(text(f"ALTER TABLE opportunities ADD COLUMN {column_name} {column_type}"))
            location_column = next((column for column in opportunity_column_info if column["name"] == "location_id"), None)
            if location_column is not None and location_column["nullable"] is False:
                connection.execute(text("ALTER TABLE opportunities RENAME TO opportunities_legacy_location_required"))
                connection.execute(
                    text(
                        """
                        CREATE TABLE opportunities (
                            id INTEGER NOT NULL,
                            company_id INTEGER NOT NULL,
                            location_id INTEGER,
                            primary_contact_id INTEGER,
                            name VARCHAR(255) NOT NULL,
                            stage VARCHAR(19) NOT NULL,
                            primary_product VARCHAR(15),
                            internet_probability INTEGER NOT NULL,
                            revenue_potential_score INTEGER NOT NULL,
                            cross_sell_score INTEGER NOT NULL,
                            priority_score INTEGER NOT NULL,
                            estimated_internet_units INTEGER NOT NULL,
                            estimated_mobile_lines INTEGER NOT NULL,
                            estimated_voice_units INTEGER NOT NULL,
                            estimated_video_units INTEGER NOT NULL,
                            estimated_mrr NUMERIC(12, 2),
                            expected_close_date DATE,
                            next_action VARCHAR(255),
                            next_action_date DATE,
                            lost_reason TEXT,
                            notes TEXT,
                            score_reason TEXT,
                            ai_summary TEXT,
                            is_active BOOLEAN DEFAULT 1 NOT NULL,
                            archived_at DATETIME,
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL,
                            PRIMARY KEY (id),
                            CONSTRAINT ck_opportunities_internet_probability CHECK (internet_probability BETWEEN 0 AND 100),
                            CONSTRAINT ck_opportunities_revenue_score CHECK (revenue_potential_score BETWEEN 0 AND 100),
                            CONSTRAINT ck_opportunities_cross_sell_score CHECK (cross_sell_score BETWEEN 0 AND 100),
                            CONSTRAINT ck_opportunities_priority_score CHECK (priority_score BETWEEN 0 AND 100),
                            FOREIGN KEY(company_id) REFERENCES companies (id),
                            FOREIGN KEY(location_id) REFERENCES locations (id),
                            FOREIGN KEY(primary_contact_id) REFERENCES contacts (id)
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO opportunities (
                            id, company_id, location_id, primary_contact_id, name, stage, primary_product,
                            internet_probability, revenue_potential_score, cross_sell_score, priority_score,
                            estimated_internet_units, estimated_mobile_lines, estimated_voice_units,
                            estimated_video_units, estimated_mrr, expected_close_date, next_action,
                            next_action_date, lost_reason, notes, score_reason, ai_summary, is_active,
                            archived_at, created_at, updated_at
                        )
                        SELECT
                            id, company_id, location_id, primary_contact_id, name, stage, primary_product,
                            internet_probability, revenue_potential_score, cross_sell_score, priority_score,
                            estimated_internet_units, estimated_mobile_lines, estimated_voice_units,
                            estimated_video_units, estimated_mrr, expected_close_date, next_action,
                            next_action_date, lost_reason, notes, score_reason, ai_summary, is_active,
                            archived_at, created_at, updated_at
                        FROM opportunities_legacy_location_required
                        """
                    )
                )
                connection.execute(text("DROP TABLE opportunities_legacy_location_required"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_opportunities_company_id ON opportunities (company_id)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_opportunities_location_id ON opportunities (location_id)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_opportunities_primary_contact_id ON opportunities (primary_contact_id)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_opportunities_stage ON opportunities (stage)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_opportunities_expected_close_date ON opportunities (expected_close_date)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_opportunities_next_action_date ON opportunities (next_action_date)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_opportunities_archived_at ON opportunities (archived_at)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_opportunities_is_active ON opportunities (is_active)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_opportunities_primary_product ON opportunities (primary_product)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_opportunities_company_stage ON opportunities (company_id, stage)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_opportunities_location_stage ON opportunities (location_id, stage)"))
            connection.execute(text("UPDATE opportunities SET stage = 'APPOINTMENT_SET' WHERE stage = 'APPOINTMENT'"))
            connection.execute(text("UPDATE opportunities SET stage = 'PROPOSAL_SENT' WHERE stage = 'QUOTE'"))
            connection.execute(text("UPDATE opportunities SET stage = 'CLOSED_WON' WHERE stage = 'WON'"))
            connection.execute(text("UPDATE opportunities SET stage = 'CLOSED_LOST' WHERE stage = 'LOST'"))
            connection.execute(text("UPDATE opportunities SET stage = 'ATTEMPTING_CONTACT' WHERE stage = 'CONTACT_ATTEMPTED'"))
            connection.execute(text("UPDATE opportunities SET stage = 'NEW' WHERE stage = 'RESEARCHING'"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_opportunities_active_next_action ON opportunities (is_active, next_action_date)"))

        if "opportunity_products" in table_names:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_opportunity_products_opportunity_product_code "
                    "ON opportunity_products (opportunity_id, product_code)"
                )
            )
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_opportunity_products_product ON opportunity_products (product_id)"))

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
