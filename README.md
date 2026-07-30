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

The app currently includes:

- Dashboard: monthly sales performance, commission progress, next-tier forecast,
  bonus progress, product performance, and sales summary.
- Companies: browse active companies by default, optionally show archived
  companies, open a company detail view, edit company information, manage
  locations, and manage contacts.

Company management supports commercial and residential/SOHO locations, contact
assignment to locations, and decision-maker contacts. Companies can be archived
and restored without deleting related locations, contacts, opportunities,
activities, tasks, or sales. Contacts and locations can be marked inactive and
restored while preserving historical relationships.

Lead source is standardized to `AE Found` or `Referral`. Referral companies
require a referral partner. The current referral partner foundation supports
creating or selecting partners from company create/edit forms and stores partner
identity, organization, Spectrum partner reference, source metadata, and active
status.

No referral compensation, payment, cash, lunch expense, referral analytics,
Opportunities UI, or Sales UI is included in this sprint.

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
