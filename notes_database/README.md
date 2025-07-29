# notes_database

This directory provides the foundational database layer for the Personal Notes Manager application.

## Components

- **models/**
  - SQLAlchemy models for users and notes.
- **db.py**
  - Database session and base configuration.
- **init_db.py**
  - Script to initialize or migrate the database.
- **alembic/**
  - (OPTIONAL, not generated here) Put Alembic migration configs here if using migrations.

## Requirements

- Python 3.9+
- SQLAlchemy
- (Optional) Alembic for migrations

## Environment Variables

See `.env.example` for required database configuration.

## Setup Example

```sh
pip install sqlalchemy psycopg2-binary
```

To initialize the database (creates tables):
```sh
python init_db.py
```
