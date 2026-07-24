from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATA_DIR / "prospector_ai.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# `check_same_thread=False` allows Streamlit reruns to share the engine safely.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base class for future SQLAlchemy models."""
