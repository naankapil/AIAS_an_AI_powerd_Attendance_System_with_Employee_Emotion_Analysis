# AIAS: AI-Powered Attendance & Emotion Monitoring System  
**Enhancing Workplace Well-being with AI**

----------------------------------------------------------

## Overview

**AIAS** is a Python-based desktop application that combines **facial recognition** and **emotion analysis** to automate employee attendance and monitor emotional trends. Designed for offline use, it aims to improve HR insights and promote employee well-being.

Developed by **Kathiramalairajah Kapilaraj**, Sri Lanka.

---

## Key Features

- **Facial Recognition:** Fast, accurate attendance via real-time face detection.
- **Emotion Detection:** Identifies emotions (Happy, Sad, Neutral, etc.) at check-in using Deep Learning.
- **Offline Functionality:** Runs without internet; stores all data locally.
- **Admin Panel:** Includes employee management, log filtering/exporting, emotion dashboards, and notification alerts.
- **Data-Driven Insights:** Flags emotion/attendance streaks to support mental wellness tracking.

---

## Technology Stack

- **Language:** Python 3.10.0
- **Libraries:** `face_recognition`, `deepface`, `opencv-python`, `tensorflow`, `keras`, `sqlite3`, `tkinter`, `matplotlib`, `Pillow`
- **AI Models:** HOG & CNN (Face Recognition), Pre-trained CNN (Emotion Detection)
- **Storage:** SQLite (local DB), file system for image data

---

## Installation

1. **Install Python 3.x**  
2. *(Optional)* Clone repo:  
   ```bash
   git clone https://github.com/YourUsername/AIAS.git
   cd AIAS
   ```
3. **Setup Environment**  
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # macOS/Linux
   ```
4. **Install Dependencies**  
   ```bash
   pip install -r requirements.txt
   ```
5. **Run Application**  
   ```bash
   python main_app_tk.py
   ```

---

## Project Structure (Highlights)

- `main_app_tk.py` – Main GUI application  
- `face_engine.py`, `emotion_engine.py` – Face & emotion recognition logic  
- `admin_logic.py`, `data_manager.py` – Backend and database operations  
- `attendance_system.db` – SQLite database (auto-created)

---

## License

This project is under the [MIT License](LICENSE.md).
