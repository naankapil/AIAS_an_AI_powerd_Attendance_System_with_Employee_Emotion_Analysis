# camera_test.py (This will be integrated into the Tkinter UI later)
import cv2
import time

# --- Placeholder functions (replace with actual imports later) ---
# from face_engine import FaceRecognitionSystem
# from emotion_engine import detect_emotion_from_face
# from data_manager import log_attendance # You'll need to write this function

# --- Dummy Recognition/Emotion ---
class DummyFaceSystem:
    def recognize_faces_in_frame(self, frame):
        h, w, _ = frame.shape
        if h > 50 and w > 50:
             name = "ID: EMP001" if int(time.time()) % 10 < 5 else "Unknown"
             emp_id = "EMP001" if name != "Unknown" else None
             box = (h//4, 3*w//4, 3*h//4, w//4) # Simulated box
             return [(emp_id, name, box)]
        return []

def dummy_detect_emotion(face_crop):
    emotions = ['happy', 'neutral', 'sad', 'neutral']
    return emotions[int(time.time()) % len(emotions)]

def dummy_log_attendance(emp_id, emotion):
    print(f"ATTENDANCE LOGGED: ID={emp_id}, Emotion={emotion}, Time={time.strftime('%Y-%m-%d %H:%M:%S')}")
    return True
# --- End Dummy ---


def run_attendance_mode():
    # Initialize Face Recognition (Use Dummy for now)
    face_sys = DummyFaceSystem()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened(): print("Error: Cannot open camera."); return

    logged_today = set()
    log_cooldown_seconds = 5
    last_log_time = {}
    process_this_frame = True

    while True:
        ret, frame = cap.read()
        if not ret: print("Error: Can't receive frame. Exiting ..."); break

        recognized_faces_info = []
        if process_this_frame:
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_small_frame = small_frame[:, :, ::-1] # BGR to RGB
            recognized_faces_info = face_sys.recognize_faces_in_frame(rgb_small_frame)

        for employee_id, name, (top, right, bottom, left) in recognized_faces_info:
            top *= 2; right *= 2; bottom *= 2; left *= 2 # Scale back up

            if employee_id is not None and employee_id != "Unknown":
                 current_time = time.time()
                 if employee_id not in logged_today:
                      if employee_id not in last_log_time or (current_time - last_log_time[employee_id]) > log_cooldown_seconds:
                           face_crop = frame[top:bottom, left:right]
                           emotion = dummy_detect_emotion(face_crop)
                           success = dummy_log_attendance(employee_id, emotion)
                           if success:
                                logged_today.add(employee_id)
                                last_log_time[employee_id] = current_time
                                display_name = f"{name} ({emotion})" if emotion else name
                                color = (0, 255, 0) # Green logged
                           else: display_name = f"{name} (Log Failed)"; color = (0, 165, 255) # Orange fail
                      else: display_name = f"{name} (Logged)"; color = (0, 255, 0) # Green recently logged
                 else: display_name = f"{name} (Already Logged)"; color = (0, 255, 255) # Yellow already today
            else: display_name = "Unknown"; color = (0, 0, 255) # Red unknown

            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.rectangle(frame, (left, bottom - 25), (right, bottom), color, cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, display_name, (left + 6, bottom - 6), font, 0.6, (255, 255, 255), 1)

        cv2.imshow('Attendance Camera - Press Q to Quit', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release(); cv2.destroyAllWindows(); print("Camera released.")

if __name__ == '__main__':
    run_attendance_mode()