import sys

import psycopg2

try:
    # Connect to the database
    # Using the credentials from the open file 'check_schema.py' seen previously or 'fix_notes_db.py'
    conn = psycopg2.connect("postgresql://paperterrace:9809@127.0.0.1:5433/paperterrace")
    cur = conn.cursor()

    # Get columns of 'notes' table
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'notes';
    """)
    rows = cur.fetchall()
    print("Columns in 'notes' table:")
    found_paper_id = False
    for row in rows:
        print(f" - {row[0]}: {row[1]}")
        if row[0] == "paper_id":
            found_paper_id = True

    if not found_paper_id:
        print("\nMISSING: paper_id column is missing!")
    else:
        print("\nOK: paper_id column exists.")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
finally:
    if "conn" in locals() and conn:
        conn.close()
