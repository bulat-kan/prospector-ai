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

## Useful CLI Checks

```bash
python -c "import app.database"
python -m app.analytics
```
