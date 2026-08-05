# Prospector AI

Local Python and Streamlit MVP for prospecting workflows, monthly sales analytics,
and configurable commission projections.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pip install -e .
```

## Database Initialization

The SQLite database is stored at `data/prospector_ai.db`.

```bash
python -m app.init_db
```

## Demo Data

Seed deterministic demo data, including July 2026 sales and commission
configuration:

```bash
python -m app.seed_demo
```

July 2026 contains deterministic sales data for dashboard testing.

## Tests

```bash
pytest -v
```

## Streamlit Dashboard

```bash
streamlit run app/ui.py
```

## UI Architecture

[app/ui.py](app/ui.py) is the Streamlit entry point. It handles page
configuration, sidebar navigation, and routing only.

Page-level coordination lives in `app/views/`:

- `dashboard_page.py`
- `companies_page.py`

Focused reusable UI sections live in `app/components/`, including company,
location, contact, referral, and flash-message components. New views should be
added under `app/views/`, and new forms/components should be added under
`app/components/`.

New forms must reuse shared validators and normalizers from `app.validation` and
controlled option lists from `app.constants`. Keep database writes in CRUD or
service modules rather than UI components.

## Commission Foundation

Commission-cycle helpers live in `app.commission_cycle`. Cycles run from the
29th through the 28th of the following month, such as `Jul 29 – Aug 28, 2026`.

Shared product catalog constants, commission statuses, and fulfillment statuses
live in `app.constants`. The shared location type list now supports SMB, SOHO,
and B&R. Business-rule notes are documented in
[docs/commission_foundation.md](docs/commission_foundation.md).

## Opportunity Backend Foundation

Opportunity backend models, validation, CRUD/service functions, DTOs, and audit
checks are available for future UI work. There is no Opportunities UI yet.

Opportunity product detail is stored in `opportunity_products` rows linked to
the Product catalog. Legacy opportunity estimate fields remain compatibility
summaries. Closed Won is pipeline state only; commission is still driven by
future Sales/SaleItems after installation or activation. Details are documented
in [docs/opportunities.md](docs/opportunities.md).

Run focused opportunity tests with:

```bash
pytest -v tests/test_opportunities.py
```

The app currently includes:

- Dashboard: monthly sales performance, commission progress, next-tier forecast,
  bonus progress, product performance, and sales summary.
- Companies: browse active companies by default, optionally show archived
  companies, open a company detail view, edit company information, manage
  locations, and manage contacts.
- Opportunities: browse and filter opportunities, add opportunities with product
  estimates, open detail records, edit pipeline fields, manage opportunity
  products, and archive or restore opportunities.

Company management supports commercial and residential/SOHO locations, contact
assignment to locations, and decision-maker contacts. Companies can be archived
and restored without deleting related locations, contacts, opportunities,
activities, tasks, or sales. Contacts and locations can be marked inactive and
restored while preserving historical relationships.

Contact data quality rules:

- Contact email is optional, but supplied values must look like
  `name@company.com` and are stored lowercase.
- At least a first name or last name is required. Names are trimmed, repeated
  spaces are collapsed, and common capitalization is normalized while preserving
  apostrophes and hyphens.
- Contact title is selected from common CRM titles. `Other` stores the supplied
  custom title, and existing custom titles remain editable as `Other`.
- Decision Role is separate from Primary Contact. Decision Role can be Unknown,
  Decision Maker, Influencer, or Gatekeeper. Primary Contact is a separate
  checkbox and does not imply decision-maker status.
- Assigned Location defaults to Unassigned. Stored values use nullable
  `location_id`; inactive assigned locations remain historically linked and are
  shown with an inactive indicator.

Lead source is standardized to `AE Found` or `Referral`. Referral companies
require a referral partner. The current referral partner foundation supports
creating or selecting partners from company create/edit forms and stores partner
identity, organization, Spectrum partner reference, source metadata, and active
status.

Opportunity workflow rules:

- Open stages require a next action and follow-up date.
- Closed Won does not count toward commission until qualifying services are
  installed or mobile lines are activated.
- Opportunity product rows store estimated quantity and estimated incremental
  MRR. Actual commission remains driven by Sales/SaleItems.
- Archived opportunities are hidden by default, visible with Show archived, and
  can be restored.

No referral compensation, payment, cash, lunch expense, referral analytics, or
Sales UI is included in this sprint.

## Data Quality Audit

Run an audit without modifying data:

```bash
python -m app.audit_data
```

The audit reports company, location, contact, referral partner, and opportunity
issues by record type and ID. It makes no changes by default and returns a
nonzero status when issues are found. `--fix` is intentionally deferred for now;
cleanup should be performed explicitly after reviewing the audit output.

Validation responsibility:

- UI: field-specific messages, conditional fields, preserving form values, and
  friendly formatting.
- CRUD: business validation, normalization, rollback safety, and domain
  `ValidationError` handling.
- Database: existing SQLAlchemy field types, foreign keys, enum storage, and
  safe additive schema compatibility. Complex email/name/location cleanup rules
  remain in CRUD/audit rather than SQLite constraints to avoid unsafe table
  rebuilds against legacy local data.

Shared standards live in [docs/data_standards.md](docs/data_standards.md).
Before adding any new input field, search for an existing validator, normalizer,
display helper, and controlled option list. Do not duplicate validation logic.
Every new UI page, script, import, future API, and CRUD path should flow through:
UI -> CRUD -> `app.validation` helpers -> `app.constants` values.

## Development Reset

To deliberately recreate the local development SQLite database and reseed demo
data:

```bash
python -m app.reset_demo_data --yes
```

Without `--yes`, the command prints the target database path and exits without
changing data. The reset command is destructive, development-only, validates
that it is operating on the project-local `data/prospector_ai.db`, disposes the
SQLAlchemy engine, removes the SQLite file, initializes the schema, and reseeds
demo data. Stop Streamlit first if it is running and holding the SQLite file.
Reset is never run from app startup, `init_db`, or `seed_demo`.

Validate the reset result with:

```bash
python -m app.audit_data
```

## Salesforce Import Foundation

Salesforce CSV/XLSX importing is planned but not implemented yet. Company,
location, and contact records include nullable source metadata fields:

- `source_system`
- `external_id`
- `last_imported_at`

Manual records can leave these fields blank. When `source_system` and
`external_id` are supplied, both values are required and the pair is treated as a
unique external record identity.

## Useful CLI Checks

```bash
python -c "import app.database"
python -m app.analytics
```
