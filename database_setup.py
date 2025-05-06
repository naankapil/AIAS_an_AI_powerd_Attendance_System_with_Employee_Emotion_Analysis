# database_setup.py (Added Department column and Cascade Delete)
import sqlite3
import hashlib
import os

DATABASE_FILE = 'attendance_system.db'
DEFAULT_ADMIN_PASSWORD = 'admin'

def setup_database():
    """Creates/Updates the database and necessary tables.
       Adds 'department' column if missing. Ensures cascade delete.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # --- Employees Table ---
        # Check if 'department' column exists first
        cursor.execute("PRAGMA table_info(employees)")
        columns = [info[1] for info in cursor.fetchall()]
        employees_table_exists = 'employee_id' in columns # Basic check if table exists

        if not employees_table_exists:
             # Create employees table if it doesn't exist at all
             print("Creating employees table...")
             cursor.execute('''
                 CREATE TABLE employees (
                     employee_id TEXT PRIMARY KEY NOT NULL,
                     name TEXT NOT NULL,
                     face_encoding BLOB NOT NULL,
                     department TEXT  -- Added Department column
                 )
             ''')
        elif 'department' not in columns:
             # Add 'department' column if the table exists but column is missing
             print("Adding 'department' column to employees table...")
             cursor.execute("ALTER TABLE employees ADD COLUMN department TEXT")


        # --- Attendance Logs Table ---
        # Recreate table definition string with ON DELETE CASCADE
        attendance_logs_create_sql = '''
            CREATE TABLE IF NOT EXISTS attendance_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                detected_emotion TEXT,
                FOREIGN KEY(employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE -- Added Cascade Delete
            )
        '''
        # Check if table exists and foreign key needs update (complex to check pragmatically)
        # Simplest approach for setup script: Create if not exists with the desired FK constraint.
        # For existing databases, manually altering FKs can be complex.
        # This setup primarily ensures new databases are correct.
        cursor.execute(attendance_logs_create_sql)


        # --- Config Table (Unchanged) ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY NOT NULL,
                value TEXT NOT NULL
            )
        ''')

        # --- Admin Password (Unchanged) ---
        cursor.execute("SELECT value FROM config WHERE key = 'admin_password_hash'")
        if cursor.fetchone() is None:
            print(f"Setting default admin password '{DEFAULT_ADMIN_PASSWORD}'...")
            salt = os.urandom(16); hashed_password = hashlib.pbkdf2_hmac('sha256', DEFAULT_ADMIN_PASSWORD.encode('utf-8'), salt, 100000)
            salt_hex = salt.hex(); hashed_password_hex = hashed_password.hex()
            cursor.execute("INSERT INTO config (key, value) VALUES (?, ?)", ('admin_password_salt', salt_hex))
            cursor.execute("INSERT INTO config (key, value) VALUES (?, ?)", ('admin_password_hash', hashed_password_hex))
            print("Default admin password set securely.")

        conn.commit()
        print(f"Database '{DATABASE_FILE}' setup/update/verification complete.")

    except sqlite3.Error as e:
        print(f"Database setup/update error: {e}")
        if conn: conn.rollback() # Rollback changes on error
    except Exception as e:
        print(f"An unexpected error occurred during database setup/update: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    print("Running database setup/update...")
    setup_database()
    print("Database setup/update script finished.")