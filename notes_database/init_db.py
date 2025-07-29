"""
Database initialization/migration script.

Run this script to create all required tables in the database.
"""
from db import engine
from models import Base

# PUBLIC_INTERFACE
def init_db():
    """Initializes the database by creating all tables if they do not exist."""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("Database tables created successfully.")
