import os
from unittest.mock import patch

import pytest

from src.providers.cloud_sql_storage import CloudSQLStorage
from src.providers.storage_provider import SQLiteStorage


def test_sqlite_storage_instantiation(temp_db):
    """Verify that SQLiteStorage can be instantiated (no missing abstract methods)."""
    try:
        # Use memory database for testing
        _ = SQLiteStorage(db_path=temp_db)
    except TypeError as e:
        pytest.fail(f"SQLiteStorage is still abstract or has missing methods: {e}")


def test_cloud_sql_storage_instantiation():
    """Verify that CloudSQLStorage can be instantiated (no missing abstract methods)."""
    # Mock DB connection and migration to avoid side effects
    with (
        patch("src.providers.cloud_sql_storage.CloudSQLStorage._get_connection", return_value=None),
        patch("src.providers.cloud_sql_storage.CloudSQLStorage.init_tables", return_value=None),
        patch("src.providers.cloud_sql_storage.CloudSQLStorage._migrate_tables", return_value=None),
        patch.dict(
            os.environ,
            {
                "GCP_PROJECT_ID": "test-project",
                "DB_USER": "test-user",
                "DB_NAME": "test-db",
                "AI_PROVIDER": "gemini",  # Prevent vertex init if possible
            },
        ),
    ):
        try:
            _ = CloudSQLStorage()
        except TypeError as e:
            pytest.fail(f"CloudSQLStorage is still abstract or has missing methods: {e}")
        except Exception as e:
            # TypeError is what we care about (abstract methods)
            if "TypeError" in str(type(e)):
                pytest.fail(f"CloudSQLStorage failed abstract check: {e}")
            # Other runtime errors can be ignored as they happen AFTER instantiation check
