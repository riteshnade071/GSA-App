"""Adds new columns to tables that already exist (create_all never alters tables). Safe to run any number of times."""
from sqlalchemy import inspect, text
from app.database import engine

NEW_COLUMNS = [
    ("opportunities", "application_steps", "JSON"),
    ("opportunities", "application_steps_hi", "JSON"),
    ("opportunities", "state_basis", "VARCHAR"),   # domicile | institute | both
    ("opportunities", "amount_text", "VARCHAR"),   # short "how much" line for the card
    ("profiles", "study_state", "VARCHAR"),
    ("users", "email", "VARCHAR"),
    ("users", "verified_via", "VARCHAR"),
    ("saved_opportunities", "application_id", "VARCHAR"),
    ("saved_opportunities", "applied_on", "TIMESTAMP"),        # state of the student's college
]


def ensure_columns():
    insp = inspect(engine)
    tables = insp.get_table_names()
    for table, col, typ in NEW_COLUMNS:
        if table in tables and col not in [c["name"] for c in insp.get_columns(table)]:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
