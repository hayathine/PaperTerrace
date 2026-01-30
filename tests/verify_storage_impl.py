import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.providers.cloud_sql_storage import CloudSQLStorage
from src.providers.storage_provider import SQLiteStorage


def test_instantiation():
    print("Testing SQLiteStorage instantiation...")
    try:
        # We use a temp db path to avoid messing with real data
        sqlite = SQLiteStorage(db_path=":memory:")
        print("✅ SQLiteStorage instantiated successfully.")
    except TypeError as e:
        print(f"❌ SQLiteStorage failed: {e}")
        return False

    print("\nTesting CloudSQLStorage instantiation...")
    try:
        # Note: CloudSQLStorage __init__ might try to connect or use env vars
        # We just want to check if it can be instantiated (i.e. all abstract methods are there)
        # We might need to mock connectivity or environment
        os.environ["INSTANCE_CONNECTION_NAME"] = "test:test:test"
        os.environ["DB_USER"] = "test"
        os.environ["DB_PASS"] = "test"
        os.environ["DB_NAME"] = "test"

        # We don't call init_tables here because it would fail without a real DB
        # But we want to check if the CLASS can be instantiated.
        # Actually, __init__ calls init_tables. We can monkeypatch it.

        original_init_tables = CloudSQLStorage.init_tables
        CloudSQLStorage.init_tables = lambda self: None
        CloudSQLStorage._migrate_tables = lambda self: None

        cloudsql = CloudSQLStorage()
        print("✅ CloudSQLStorage instantiated successfully (abstract methods check passed).")

        # Restore
        CloudSQLStorage.init_tables = original_init_tables

    except TypeError as e:
        print(f"❌ CloudSQLStorage failed: {e}")
        return False
    except Exception as e:
        # Connection errors are expected since we don't have a real DB
        print(
            f"ℹ️ CloudSQLStorage encountered an expected runtime error (connection), but it passed the abstract class check: {e}"
        )

    return True


if __name__ == "__main__":
    if test_instantiation():
        print("\nAll storage implementations are valid.")
        sys.exit(0)
    else:
        print("\nValidation failed.")
        sys.exit(1)
