from app.providers.cloud_sql_storage import CloudSQLStorage
try:
    s = CloudSQLStorage()
    print("Success instantiation")
except TypeError as e:
    print(f"FAILED: {e}")
