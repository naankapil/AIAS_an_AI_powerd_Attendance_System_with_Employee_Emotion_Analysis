# data_manager.py (Fixes Delete Constraint, Update Photo NoneType Error - ADDED DEBUGGING)
import sqlite3
import face_recognition
import numpy as np
import pickle
import os
import datetime
import cv2
import traceback # For detailed error printing

DATABASE_FILE = 'attendance_system.db'

# --- Encoding Serialization/Deserialization ---
def serialize_encoding(encoding_array):
    # Simple check for numpy array (can be expanded if needed)
    if not isinstance(encoding_array, np.ndarray):
        raise TypeError("Input for serialization must be a NumPy array.")
    return pickle.dumps(encoding_array)

def deserialize_encoding(encoding_blob):
    # Simple check for bytes type
    if not isinstance(encoding_blob, bytes):
        raise TypeError("Input for deserialization must be bytes.")
    try:
        # Attempt to deserialize using pickle
        return pickle.loads(encoding_blob)
    except Exception as pe:
        # Catch potential errors during deserialization (e.g., corrupted data)
        print(f"Error deserializing encoding data: {pe}")
        raise # Re-raise the exception to be handled by the caller

# --- Employee Management ---
def add_employee(employee_id, name, face_image_path, department=None):
    conn = None # Initialize connection variable

    # --- ADDED: Pre-check if ID exists *before* processing image ---
    employee_exists_before_insert = False
    db_path = os.path.abspath(DATABASE_FILE) # Get absolute path for clarity in logs
    print(f"DEBUG: Checking database file at: {db_path}")
    try:
        if not os.path.exists(db_path):
            print(f"DEBUG: Database file does not exist before pre-check for ID '{employee_id}'. This is expected if DB was just deleted.")
        else:
            # Connect to check existence if DB file is present
            print(f"DEBUG: Database file exists. Performing pre-check for ID '{employee_id}'...")
            conn_check = sqlite3.connect(DATABASE_FILE)
            cursor_check = conn_check.cursor()
            # Execute SELECT query to check for the employee_id
            cursor_check.execute("SELECT 1 FROM employees WHERE employee_id = ?", (employee_id,))
            if cursor_check.fetchone(): # fetchone() returns a tuple if found, None otherwise
                employee_exists_before_insert = True # Set flag if found
            conn_check.close() # Close the check connection
            print(f"DEBUG: Pre-check complete for ID '{employee_id}'. Found existing? {employee_exists_before_insert}")
    except Exception as e_check:
        # Catch errors during the pre-check itself
        print(f"!!! ERROR during pre-check for employee ID {employee_id}: {e_check}")
        # Depending on the error, you might want to stop enrollment here
        # For now, we'll print the error and continue to see if INSERT fails later
        # return False
    # --- END ADDED PRE-CHECK ---

    print(f"DEBUG: Proceeding with add_employee details for ID '{employee_id}'. Existed according to pre-check? {employee_exists_before_insert}") # Log result of pre-check

    # Optional: Return early if pre-check found it - uncomment if needed for strict debugging
    # if employee_exists_before_insert:
    #    print(f"DEBUG: Pre-check confirmed ID '{employee_id}' exists. Aborting add_employee before image processing.")
    #    return False

    # --- Start Image Processing and Database Interaction ---
    try:
        print(f"Loading image from: {face_image_path}")
        # Load the image using OpenCV
        image_bgr = cv2.imread(face_image_path)
        if image_bgr is None:
             print(f"Error: Cannot read image file {face_image_path}. Check path and permissions."); return False

        # Convert image to RGB format (required by face_recognition library)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        # Validate image format and dimensions (basic checks)
        if not isinstance(image_rgb, np.ndarray) or image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
             print("Error: Invalid image format/dimensions after loading/conversion."); return False

        # Ensure image dtype is uint8 (sometimes needed for face_recognition)
        if image_rgb.dtype != np.uint8:
             try:
                 image_rgb = image_rgb.astype(np.uint8); print("Info: Converted image dtype to uint8.")
             except Exception as conv_err:
                 print(f"Error converting image dtype to uint8: {conv_err}"); return False

        # Ensure image data is contiguous in memory (sometimes required by C libraries)
        image_cont = np.ascontiguousarray(image_rgb)

        # --- Face Detection and Encoding ---
        print("Finding face locations (using CNN model - might be slow)...")
        # Use CNN model for potentially better accuracy finding faces
        face_locations = face_recognition.face_locations(image_cont, model='cnn')
        if not face_locations:
             print(f"Error: No face found in the image: {face_image_path}"); return False # Critical error if no face
        if len(face_locations) > 1:
             print(f"Warning: Multiple faces found in {face_image_path}. Using the first one detected.")
             # Consider adding logic to select the largest face or prompt user if multiple faces is an issue

        print("Generating face encoding (using 'small' model)...")
        # Generate encoding for the first detected face location
        # 'small' model is faster for encoding than the 'large' one
        face_encodings = face_recognition.face_encodings(image_cont, known_face_locations=[face_locations[0]], model='small')

        # Check if encoding generation was successful
        if not face_encodings:
             print(f"Error: Could not generate face encoding for the detected face."); return False

        face_encoding = face_encodings[0] # Get the first (and likely only) encoding
        serialized_encoding = serialize_encoding(face_encoding) # Serialize numpy array to bytes using pickle
        print(f"DEBUG: Face processed successfully for ID '{employee_id}'. Encoding size: {len(serialized_encoding)} bytes.") # DEBUG LINE

        # --- Database Operation ---
        conn = sqlite3.connect(DATABASE_FILE) # Connect to the database
        cursor = conn.cursor()
        print(f"DEBUG: Connected to DB for insert operation (ID: '{employee_id}').") # DEBUG LINE
        print(f"Inserting into database: ID={employee_id}, Name={name}, Dept={department}")
        print(f"DEBUG: About to execute INSERT for ID '{employee_id}'...") # DEBUG LINE

        # Execute the INSERT statement
        cursor.execute("INSERT INTO employees (employee_id, name, face_encoding, department) VALUES (?, ?, ?, ?)",
                       (employee_id, name, serialized_encoding, department))

        print(f"DEBUG: INSERT command executed for ID '{employee_id}'. About to commit.") # DEBUG LINE
        conn.commit() # Commit the transaction if INSERT was successful
        print(f"DEBUG: Commit successful for ID '{employee_id}'.") # DEBUG LINE
        print(f"Employee {name} (ID: {employee_id}) added successfully."); return True # Return True on success

    except sqlite3.IntegrityError as ie: # Catch primary key violation (duplicate ID)
        # --- Specific handling for duplicate key error ---
        print(f"!!! DB IntegrityError caught for ID '{employee_id}': {ie}") # More specific print
        print(f"!!! This usually means the Employee ID '{employee_id}' already exists in the database table 'employees'.") # Explain
        if conn:
            print("DEBUG: Rolling back transaction due to IntegrityError.") # DEBUG LINE
            try:
                conn.rollback() # Rollback any partial transaction
            except Exception as rb_err:
                print(f"!!! Error during rollback after IntegrityError: {rb_err}")
        return False # Return False on duplicate

    except sqlite3.Error as e: # Catch other specific database errors
         print(f"!!! DB Error (non-Integrity) during add_employee for ID '{employee_id}': {e}") # DEBUG LINE
         if conn:
              print("DEBUG: Rolling back transaction due to other DB Error.") # DEBUG LINE
              try:
                  conn.rollback()
              except Exception as rb_err:
                  print(f"!!! Error during rollback after other DB Error: {rb_err}")
         return False

    except FileNotFoundError:
        # Handle case where the image file path doesn't exist
        print(f"Error: Image file not found: {face_image_path}"); return False
    except RuntimeError as rte:
        # Handle potential runtime errors from face_recognition library
        print(f"!!! RUNTIME ERROR during face processing for ID '{employee_id}': {rte}"); return False

    except Exception as e: # Catch any other unexpected errors during the process
        print(f"!!! Unexpected error during add_employee for ID '{employee_id}': {e}"); traceback.print_exc(); # Print detailed traceback
        if conn:
             print("DEBUG: Rolling back transaction due to unexpected error.") # DEBUG LINE
             try:
                 conn.rollback() # Rollback on unexpected errors too
             except Exception as rb_err:
                  print(f"!!! Error during rollback after unexpected error: {rb_err}")
        return False

    finally:
        # Ensure the database connection is closed in all cases
        if conn:
             print(f"DEBUG: Closing DB connection in finally block for add_employee (ID: '{employee_id}').") # DEBUG LINE
             conn.close()

# --- (Rest of the functions in data_manager.py remain unchanged) ---

def get_all_employees():
    # ... (Keep existing code - unchanged) ...
    conn = None; employees = []
    try:
        conn = sqlite3.connect(DATABASE_FILE); cursor = conn.cursor()
        try: cursor.execute("SELECT employee_id, name, department FROM employees ORDER BY name"); employees = cursor.fetchall()
        except sqlite3.OperationalError as e:
             if 'no such column: department' in str(e):
                 print("Warning: 'department' column not found. Fetching only ID and Name.")
                 cursor.execute("SELECT employee_id, name FROM employees ORDER BY name"); employees = [(row[0], row[1], None) for row in cursor.fetchall()]
             else: raise
    except sqlite3.Error as e: print(f"Database error fetching all employees: {e}")
    except Exception as e: print(f"Unexpected error fetching employees: {e}")
    finally:
        if conn: conn.close()
    return employees

def update_employee_details(employee_id, new_name, new_department):
    # ... (Keep existing code - unchanged) ...
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE); cursor = conn.cursor()
        cursor.execute("UPDATE employees SET name = ?, department = ? WHERE employee_id = ?", (new_name, new_department, employee_id))
        conn.commit()
        if cursor.rowcount == 0: print(f"Warning: No employee found with ID '{employee_id}' to update."); return False
        print(f"Successfully updated details for employee ID: {employee_id}"); return True
    except sqlite3.Error as e:
        print(f"Database error updating details for {employee_id}: {e}")
        if conn: conn.rollback()
        return False
    except Exception as e:
        print(f"Unexpected error updating details: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

def update_employee_photo(employee_id, new_image_path):
    """Updates the face encoding for an existing employee using a new photo."""
    new_serialized_encoding = None
    try: # Try block for face processing steps
        print(f"Loading new image from: {new_image_path}")
        image_bgr = cv2.imread(new_image_path)
        if image_bgr is None: print(f"Error: Cannot read new image {new_image_path}"); return False
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        if not isinstance(image_rgb, np.ndarray) or image_rgb.ndim != 3 or image_rgb.shape[2] != 3: print("Error: Invalid new image format/dimensions."); return False
        if image_rgb.dtype != np.uint8:
            try: image_rgb = image_rgb.astype(np.uint8)
            except Exception as conv_err: print(f"Error converting new image dtype: {conv_err}"); return False
        image_cont = np.ascontiguousarray(image_rgb)
        print("Finding face locations (CNN model)...")
        face_locations = face_recognition.face_locations(image_cont, model='cnn')
        if not face_locations: print(f"Error: No face found in new image {new_image_path}"); return False
        if len(face_locations) > 1: print(f"Warning: Multiple faces found in new image. Using first one.")
        print("Generating face encoding ('small' model)...")
        face_encodings = face_recognition.face_encodings(image_cont, known_face_locations=[face_locations[0]], model='small')

        # --- FIX: Check if encoding was successful ---
        if not face_encodings:
             print(f"Error: Could not generate encoding from new image.")
             return False
        # --- End Fix ---

        new_face_encoding = face_encodings[0]
        new_serialized_encoding = serialize_encoding(new_face_encoding)
        print(f"New encoding generated (Size: {len(new_serialized_encoding)} bytes).") # len() is safe now

    except FileNotFoundError: print(f"Error: New image file not found: {new_image_path}"); return False
    except RuntimeError as rte: print(f"!!! RUNTIME ERROR during face processing for update: {rte}"); return False
    except cv2.error as cv_err: print(f"!!! OpenCV Error during face processing for update: {cv_err}"); return False
    except Exception as img_proc_err: print(f"Unexpected error during face processing: {img_proc_err}"); return False

    conn = None
    try: # Try block specifically for database operations
        if new_serialized_encoding is None: print("Error: Face encoding step failed, cannot update database."); return False
        conn = sqlite3.connect(DATABASE_FILE); cursor = conn.cursor()
        print(f"Updating face encoding for database ID: {employee_id}")
        cursor.execute("UPDATE employees SET face_encoding = ? WHERE employee_id = ?", (new_serialized_encoding, employee_id))
        conn.commit()
        if cursor.rowcount == 0: print(f"Warning: No employee found with ID '{employee_id}' to update photo encoding."); return False
        else: print(f"Successfully updated face encoding for employee ID: {employee_id}"); return True
    except sqlite3.Error as e:
        print(f"DB error updating photo for {employee_id}: {e}")
        if conn: conn.rollback()
        return False
    except Exception as e:
        print(f"Unexpected error during DB update for photo: {e}"); import traceback; traceback.print_exc()
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

def delete_employee_data(employee_id):
    """Deletes an employee record and their attendance logs manually."""
    conn = None
    deleted_logs = 0
    deleted_employee = 0
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # --- FIX: Manually delete attendance logs first (if ON DELETE CASCADE isn't reliable/present) ---
        # Although database_setup aims for ON DELETE CASCADE, this provides robustness
        print(f"Deleting attendance logs for employee ID: {employee_id}...")
        cursor.execute("DELETE FROM attendance_logs WHERE employee_id = ?", (employee_id,))
        deleted_logs = cursor.rowcount
        print(f"Deleted {deleted_logs} log records for {employee_id}.")
        # --- End Fix ---

        # Now delete the employee
        print(f"Deleting employee record for ID: {employee_id}...")
        cursor.execute("DELETE FROM employees WHERE employee_id = ?", (employee_id,))
        deleted_employee = cursor.rowcount

        if deleted_employee == 0:
            print(f"Warning: No employee found with ID '{employee_id}' to delete.")
            # If employee didn't exist, no need to rollback log deletion attempt
            conn.commit() # Commit potential log deletions even if employee delete did nothing
            return False # Indicate employee wasn't found/deleted
        else:
            print(f"Successfully deleted employee ID: {employee_id}.")
            conn.commit() # Commit after both deletes succeed (or employee delete succeeds)
            return True # Indicate successful deletion
    except sqlite3.Error as e:
        print(f"Database error deleting employee {employee_id}: {e}")
        if conn: conn.rollback() # Rollback if any error occurs during the process
        return False
    except Exception as e:
        print(f"Unexpected error deleting employee {employee_id}: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

def load_known_faces():
    # ... (Keep existing code - unchanged, but added some debug prints) ...
    known_face_encodings = []; known_face_ids = []; conn = None
    try:
        print("DEBUG: Loading known faces from database...") # DEBUG LINE
        db_path = os.path.abspath(DATABASE_FILE)
        if not os.path.exists(db_path):
            print(f"DEBUG: Database file '{db_path}' not found during load_known_faces. Returning empty lists.")
            return [], []

        conn = sqlite3.connect(DATABASE_FILE); cursor = conn.cursor()
        cursor.execute("SELECT employee_id, face_encoding FROM employees"); rows = cursor.fetchall()
        print(f"DEBUG: Found {len(rows)} rows in employees table.") # DEBUG LINE
        count = 0; error_count = 0
        for row in rows:
            employee_id = row[0]; serialized_encoding = row[1]
            try:
                 if not isinstance(serialized_encoding, bytes):
                     error_count += 1; print(f"Warning: Encoding for {employee_id} is not bytes, type is {type(serialized_encoding)}. Skipping."); continue # Added print
                 # print(f"DEBUG: Deserializing encoding for {employee_id} (size: {len(serialized_encoding)} bytes)") # Optional DEBUG
                 encoding = deserialize_encoding(serialized_encoding) # Uses pickle.loads
                 if isinstance(encoding, np.ndarray) and encoding.shape == (128,):
                     known_face_ids.append(employee_id); known_face_encodings.append(encoding); count += 1
                 else:
                     error_count += 1; print(f"Warning: Deserialized encoding for {employee_id} has wrong type/shape: {type(encoding)} / {getattr(encoding, 'shape', 'N/A')}. Skipping.") # Added print
            except Exception as pe:
                 print(f"Error deserializing or processing encoding for {employee_id}: {pe}. Skipping."); error_count += 1
        # Modified status message
        if error_count > 0: print(f"Finished loading faces. Successfully loaded: {count}. Errors/Skipped: {error_count}.")
        else: print(f"Successfully loaded {count} known faces.")
    except sqlite3.Error as e: print(f"Database error loading faces: {e}")
    except Exception as e: print(f"Unexpected error loading faces: {e}")
    finally:
        if conn: conn.close()
    return known_face_ids, known_face_encodings

def get_employee_name(employee_id):
    # ... (Keep existing code - unchanged) ...
    conn = None; name = f"ID: {employee_id}" # Default if not found or error
    if not employee_id or employee_id == "Unknown": return "Unknown"
    try:
        conn = sqlite3.connect(DATABASE_FILE); cursor = conn.cursor()
        cursor.execute("SELECT name FROM employees WHERE employee_id = ?", (employee_id,)); result = cursor.fetchone()
        if result and result[0]: name = result[0]
    except sqlite3.Error as e: print(f"DB error fetching name for {employee_id}: {e}"); name = f"DB Error ({employee_id})"
    finally:
        if conn: conn.close()
    return name

def log_attendance(employee_id, emotion):
    # ... (Keep existing code - unchanged) ...
    conn = None; log_success = False
    if not employee_id or employee_id == "Unknown": return False
    # Get current timestamp and date string
    current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'); today_date_str = datetime.date.today().isoformat()
    try:
        conn = sqlite3.connect(DATABASE_FILE); cursor = conn.cursor()
        # Check if a log already exists for this employee today
        cursor.execute("SELECT 1 FROM attendance_logs WHERE employee_id = ? AND DATE(timestamp) = ? LIMIT 1", (employee_id, today_date_str)); existing_log = cursor.fetchone()
        if existing_log is None:
            # No log exists for today, insert a new one
            cursor.execute("INSERT INTO attendance_logs (employee_id, timestamp, detected_emotion) VALUES (?, ?, ?)", (employee_id, current_timestamp, emotion if emotion else "N/A"));
            conn.commit(); log_success = True
            # print(f"DEBUG: Attendance logged successfully for {employee_id} on {today_date_str}") # Optional DEBUG
        else:
            # Log already exists for today
            log_success = False
            # print(f"DEBUG: Attendance already logged today for {employee_id}") # Optional DEBUG
    except sqlite3.Error as e:
        print(f"DATABASE: Error during log_attendance for {employee_id}: {e}");
        log_success = False # Ensure failure on error
        if conn: conn.rollback() # Rollback on error
    finally:
        if conn: conn.close()
    return log_success

if __name__ == '__main__':
    # Example usage or testing can be added here if needed
    print("Running data_manager.py directly (for testing or utility functions)...")
    # Example: Test loading faces
    # ids, encs = load_known_faces()
    # print(f"Loaded {len(ids)} IDs.")
    pass