# Prospector AI

Local Python and Streamlit MVP for prospecting workflows.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Database

The SQLite database is configured at:

```text
data/prospector_ai.db
```

The SQLAlchemy foundation lives in `app/database.py`. Database models have not
been added yet.

## Run

Add a Streamlit entry point when the MVP UI is ready, then run it with:

```bash
streamlit run <entrypoint>.py
```

## Import Check

```bash
python -c "import app.database"
```
