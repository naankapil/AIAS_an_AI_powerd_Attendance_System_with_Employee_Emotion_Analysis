# face_engine.py (Added Input Validation)
import face_recognition
import numpy as np
import cv2 # Only needed if doing CV operations here

class FaceRecognitionSystem:
    def __init__(self):
        """Initializes the system with empty lists for known faces."""
        self.known_face_ids = []
        self.known_face_encodings = []
        print("FaceRecognitionSystem initialized (waiting for known faces).")

    def recognize_faces_in_frame(self, rgb_frame_input):
        """Detects and recognizes faces in a single frame (HOG model)."""
        # Input Validation
        if not isinstance(rgb_frame_input, np.ndarray): print("Error face_engine: Input not numpy array."); return []
        if rgb_frame_input.ndim != 3: print(f"Error face_engine: Wrong dimensions ({rgb_frame_input.ndim})"); return []
        if rgb_frame_input.shape[2] != 3: print(f"Error face_engine: Wrong channels ({rgb_frame_input.shape[2]})"); return []
        if rgb_frame_input.dtype != np.uint8:
            print(f"Error face_engine: Wrong dtype ({rgb_frame_input.dtype}). Trying conversion.")
            try: rgb_frame_input = rgb_frame_input.astype(np.uint8, copy=False); print("Info: Converted frame to uint8.")
            except Exception as e: print(f"Error face_engine: Convert frame failed: {e}"); return []

        rgb_frame = np.ascontiguousarray(rgb_frame_input)
        face_locations = []
        face_encodings = []

        try: # Find faces using HOG (faster but less accurate than CNN)
            face_locations = face_recognition.face_locations(rgb_frame, model='hog')
        except RuntimeError as rte: print(f"!!! RUNTIME ERROR face_locations (hog): {rte}"); print(f"Input frame: dtype={rgb_frame.dtype}, shape={rgb_frame.shape}, flags={rgb_frame.flags}"); return []
        except Exception as e: print(f"!!! UNEXPECTED ERROR face_locations (hog): {e}"); return []

        if face_locations and self.known_face_encodings: # Encode faces if found and known faces exist
            try: face_encodings = face_recognition.face_encodings(rgb_frame, face_locations) # Uses 'small' model by default
            except Exception as e: print(f"Error during face_encodings: {e}"); return [('Unknown', None, loc) for loc in face_locations]

        # Recognition logic
        recognized_faces = []
        for i, loc in enumerate(face_locations):
            employee_id = "Unknown"
            if self.known_face_encodings and i < len(face_encodings):
                 current_face_encoding = face_encodings[i]
                 matches = face_recognition.compare_faces(self.known_face_encodings, current_face_encoding, tolerance=0.5) # Adjust tolerance if needed
                 face_distances = face_recognition.face_distance(self.known_face_encodings, current_face_encoding)
                 if face_distances.size > 0:
                      best_match_index = np.argmin(face_distances)
                      if matches[best_match_index]:
                           employee_id = self.known_face_ids[best_match_index]
            recognized_faces.append((employee_id, None, loc)) # Append result (ID or Unknown)
        return recognized_faces

# --- Example Usage (Keep commented out) ---
# if __name__ == '__main__': pass