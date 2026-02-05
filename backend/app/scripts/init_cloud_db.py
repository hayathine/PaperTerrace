import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from app.models.orm import Base

load_dotenv()


def init_db():
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME")

    if not all([user, password, dbname]):
        print("Error: Missing DB_USER, DB_PASSWORD, or DB_NAME environment variables.")
        return

    # Construct Database URL
    # Use standard psycopg2 driver
    DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

    print(f"Connecting to {host}:{port}/{dbname} as {user}...")

    try:
        engine = create_engine(DATABASE_URL)

        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("Connection successful!", result.scalar())

        print("Creating tables...")
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully!")

    except Exception as e:
        print(f"Failed to initialize database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    init_db()
