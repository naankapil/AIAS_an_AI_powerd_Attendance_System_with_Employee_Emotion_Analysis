# admin_logic.py (Added data reset and notification analysis logic)
import sqlite3
import hashlib
import csv
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import itertools # For groupby

DATABASE_FILE = 'attendance_system.db'

# --- Password Verification ---
def verify_admin_password(entered_password):
    conn = None
    stored_hash_hex = None
    salt_hex = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = 'admin_password_hash'")
        hash_result = cursor.fetchone()
        if hash_result:
            stored_hash_hex = hash_result[0]
        cursor.execute("SELECT value FROM config WHERE key = 'admin_password_salt'")
        salt_result = cursor.fetchone()
        if salt_result:
            salt_hex = salt_result[0]
        if stored_hash_hex and salt_hex:
            try:
                salt = bytes.fromhex(salt_hex)
                stored_hash = bytes.fromhex(stored_hash_hex)
            except ValueError as e:
                 print(f"Error decoding stored password hash or salt (invalid hex?): {e}")
                 return False
            entered_hash = hashlib.pbkdf2_hmac(
                'sha256',
                entered_password.encode('utf-8'),
                salt,
                100000
            )
            return stored_hash == entered_hash
        else:
            print("Admin password salt or hash not found in config table. Cannot verify.")
            return False
    except sqlite3.Error as e:
        print(f"Database error during password verification: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during password verification: {e}")
        return False
    finally:
        if conn:
            conn.close()

# --- Data Retrieval ---
def get_attendance_logs(start_date_str=None, end_date_str=None, employee_id=None):
    conn = None
    logs = []
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        query = """
            SELECT l.log_id, l.employee_id, e.name, l.timestamp, l.detected_emotion
            FROM attendance_logs l
            JOIN employees e ON l.employee_id = e.employee_id
        """
        filters = []
        params = []
        if employee_id:
            filters.append("l.employee_id = ?")
            params.append(employee_id)
        if start_date_str:
            try:
                datetime.strptime(start_date_str, '%Y-%m-%d')
                filters.append("DATE(l.timestamp) >= ?")
                params.append(start_date_str)
            except ValueError:
                print(f"Warning: Invalid start date format '{start_date_str}'. Ignoring filter.")
        if end_date_str:
            try:
                datetime.strptime(end_date_str, '%Y-%m-%d')
                filters.append("DATE(l.timestamp) <= ?")
                params.append(end_date_str)
            except ValueError:
                print(f"Warning: Invalid end date format '{end_date_str}'. Ignoring filter.")
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY l.employee_id, l.timestamp ASC" # Sort order for analysis
        cursor.execute(query, params)
        logs = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error retrieving logs: {e}")
    except Exception as e:
        print(f"An unexpected error occurred retrieving logs: {e}")
    finally:
        if conn:
            conn.close()
    return logs

# --- CSV Export ---
def export_logs_to_csv(filepath, logs_data):
    if not logs_data:
        print("No data provided to export.")
        return False
    try:
        headers = ['Log ID', 'Employee ID', 'Name', 'Timestamp', 'Detected Emotion']
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            writer.writerows(logs_data)
        print(f"Logs successfully exported to {filepath}")
        return True
    except IOError as e:
        print(f"Error writing CSV file {filepath}: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during CSV export: {e}")
        return False

# --- NEW: Data Reset Function ---
def reset_attendance_emotion_data():
    """
    Deletes all records from the attendance_logs table.
    Returns True on success, False on failure.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM attendance_logs")
        conn.commit()
        rows_deleted = cursor.rowcount
        print(f"Successfully deleted {rows_deleted} records from attendance_logs.")
        # Optional: Vacuum
        # conn.execute("VACUUM")
        return True
    except sqlite3.Error as e:
        print(f"Database error during data reset: {e}")
        if conn: conn.rollback()
        return False
    except Exception as e:
        print(f"An unexpected error occurred during data reset: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

# --- NEW: Notification Panel Logic ---
def analyze_notification_data(days_threshold=2, attendance_threshold=3):
    """
    Analyzes all attendance logs to find employees meeting notification criteria.
    """
    print(f"Analyzing notification data (Emotion >= {days_threshold+1} days, Attendance >= {attendance_threshold+1} days)...")
    logs = get_attendance_logs()
    if not logs:
        return {"negative_emotion_streaks": [], "attendance_streaks": []}

    negative_emotion_streaks = []
    attendance_streaks = []
    negative_emotions = {"angry", "sad"} # Case-insensitive check later

    for employee_id, group in itertools.groupby(logs, key=lambda x: x[1]):
        employee_logs = list(group)
        if not employee_logs: continue
        employee_name = employee_logs[0][2]

        daily_logs = defaultdict(list)
        for log in employee_logs:
            try:
                log_time = datetime.strptime(log[3], '%Y-%m-%d %H:%M:%S')
                log_date = log_time.date()
                daily_logs[log_date].append(log[4])
            except ValueError: continue

        sorted_dates = sorted(daily_logs.keys())
        if not sorted_dates: continue # Skip if no valid dates found

        # Emotion Streak Analysis
        current_emotion_streak = 0; last_emotion_date = None; streak_emotion = None
        first_neg_emotion_date = None # Track start of current streak
        for i, current_date in enumerate(sorted_dates):
            is_consecutive = (i > 0) and (current_date == sorted_dates[i-1] + timedelta(days=1))
            day_emotions = [str(e).lower() for e in daily_logs[current_date] if e and isinstance(e, str)]
            has_negative_emotion = any(e in negative_emotions for e in day_emotions)
            dominant_negative_emotion = next((e for e in day_emotions if e in negative_emotions), None)

            if has_negative_emotion:
                if is_consecutive and streak_emotion:
                    current_emotion_streak += 1
                else: # Start new streak or first day
                    # Check if previous streak met threshold before resetting
                    if current_emotion_streak > days_threshold and first_neg_emotion_date:
                         negative_emotion_streaks.append((employee_id, employee_name, streak_emotion.capitalize() if streak_emotion else "N/A", current_emotion_streak, first_neg_emotion_date.isoformat(), sorted_dates[i-1].isoformat()))
                    current_emotion_streak = 1
                    streak_emotion = dominant_negative_emotion
                    first_neg_emotion_date = current_date # Record start date
                last_emotion_date = current_date
            else: # End of streak or non-negative day
                if current_emotion_streak > days_threshold and first_neg_emotion_date:
                    negative_emotion_streaks.append((employee_id, employee_name, streak_emotion.capitalize() if streak_emotion else "N/A", current_emotion_streak, first_neg_emotion_date.isoformat(), sorted_dates[i-1].isoformat()))
                current_emotion_streak = 0
                streak_emotion = None
                first_neg_emotion_date = None

        if current_emotion_streak > days_threshold and first_neg_emotion_date and last_emotion_date: # Check streak ending on last day
             negative_emotion_streaks.append((employee_id, employee_name, streak_emotion.capitalize() if streak_emotion else "N/A", current_emotion_streak, first_neg_emotion_date.isoformat(), last_emotion_date.isoformat()))

        # Attendance Streak Analysis
        current_attendance_streak = 0; last_attendance_date = None
        first_att_streak_date = None # Track start of current streak
        for i, current_date in enumerate(sorted_dates):
            is_consecutive = (i > 0) and (current_date == sorted_dates[i-1] + timedelta(days=1))
            if i == 0 or not is_consecutive: # Start of a new potential streak
                 # Record previous streak if it met threshold
                 if current_attendance_streak > attendance_threshold and first_att_streak_date:
                     attendance_streaks.append((employee_id, employee_name, current_attendance_streak, first_att_streak_date.isoformat(), sorted_dates[i-1].isoformat()))
                 current_attendance_streak = 1 # Reset for current day
                 first_att_streak_date = current_date # Mark start date
            else: # Consecutive day
                 current_attendance_streak += 1
            last_attendance_date = current_date

        if current_attendance_streak > attendance_threshold and first_att_streak_date and last_attendance_date: # Check streak ending on last day
             attendance_streaks.append((employee_id, employee_name, current_attendance_streak, first_att_streak_date.isoformat(), last_attendance_date.isoformat()))

    print(f"Analysis complete. Found {len(negative_emotion_streaks)} neg emotion streaks, {len(attendance_streaks)} attendance streaks.")
    # Return structure updated to include start/end dates
    return {
        "negative_emotion_streaks": negative_emotion_streaks, # (id, name, emotion, days, start_date, end_date)
        "attendance_streaks": attendance_streaks             # (id, name, days, start_date, end_date)
    }