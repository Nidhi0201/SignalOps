"""
Database connection and session management.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database URL - defaults to the docker-compose Postgres, overridable via env
# (e.g. tests point this at an ephemeral testcontainer).
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://signalops:signalops@localhost:5432/signalops"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for FastAPI to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
