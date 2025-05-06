# main_app_tk.py (Final Version v4 - Includes L275 Syntax Fix and All Features - Updated Shutdown)
import tkinter as tk
from tkinter import ttk # Themed widgets
from tkinter import messagebox, filedialog
import cv2
from PIL import Image, ImageTk
import threading
import time
import os
import sqlite3
from datetime import datetime, date, timedelta
import calendar
import itertools
import shutil

# --- Plotting and Data Handling ---
import matplotlib
matplotlib.use('TkAgg') # Explicitly set backend BEFORE importing pyplot
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import Counter, defaultdict
import pandas as pd
import numpy as np

# --- Optional Imports for UI Enhancements ---
THEMES_AVAILABLE = False # Force standard Tk to avoid potential issues

try:
    from tkcalendar import DateEntry
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False
    print("tkcalendar not found, using standard Entry for dates. (pip install tkcalendar)")
# --- End Optional Imports ---

# --- Import your modules ---
# Ensure these files exist in the same directory
try:
    from database_setup import setup_database, DATABASE_FILE
    from data_manager import (
        add_employee, load_known_faces, get_employee_name, log_attendance,
        get_all_employees, update_employee_details, update_employee_photo, delete_employee_data
    )
    from face_engine import FaceRecognitionSystem
    from emotion_engine import detect_emotion_from_face # Uses updated emotion_engine.py
    from admin_logic import (
        verify_admin_password, get_attendance_logs, export_logs_to_csv,
        reset_attendance_emotion_data, analyze_notification_data
    )
except ImportError as e:
    print(f"FATAL ERROR: Could not import required modules: {e}")
    print("Please ensure database_setup.py, data_manager.py, face_engine.py, emotion_engine.py, and admin_logic.py are in the same directory.")
    exit()


# --- Constants ---
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
CAMERA_FRAME_WIDTH = 640
CAMERA_FRAME_HEIGHT = 480
RECOGNITION_SCALE = 0.5
LOG_COOLDOWN_SECONDS = 10
ENROLL_COUNTDOWN_SECONDS = 3
EMPLOYEE_PHOTO_DIR = "employee_photos" # Make sure this directory exists
NOTIFICATION_EMOTION_THRESHOLD = 2 # Days for negative emotion streak
NOTIFICATION_ATTENDANCE_THRESHOLD = 3 # Days for attendance streak

# --- Custom Admin Login Dialog ---
class AdminLoginDialog(tk.Toplevel):
    # ... (Keep existing AdminLoginDialog class code - unchanged) ...
    def __init__(self, parent, title="Admin Login"):
        super().__init__(parent)
        self.transient(parent); self.title(title); self.parent = parent; self.result = None; self.password_entry = None
        dialog_bg = "#f0f0f0"; label_font = ("Arial", 11); button_font = ("Arial", 10, "bold"); button_bg = "#007bff"; button_fg = "white"; button_active_bg = "#0056b3"
        self.configure(background=dialog_bg)
        frame = ttk.Frame(self, padding="20 20 20 20"); frame.pack(expand=True, fill=tk.BOTH)
        ttk.Label(frame, text="Enter Admin Password:", font=label_font).pack(pady=(0, 10))
        self.password_entry = ttk.Entry(frame, show='*', width=30, font=label_font); self.password_entry.pack(pady=(0, 20)); self.password_entry.focus_set()
        button_frame = ttk.Frame(frame); button_frame.pack()
        s_dialog = ttk.Style(self); s_dialog.configure('Dialog.TButton', font=button_font, padding=[10, 5], foreground=button_fg, background=button_bg); s_dialog.map('Dialog.TButton', background=[('active', button_active_bg)])
        ok_button = ttk.Button(button_frame, text="Login", width=10, command=self.ok, style='Dialog.TButton'); ok_button.pack(side=tk.LEFT, padx=10)
        cancel_button = ttk.Button(button_frame, text="Cancel", width=10, command=self.cancel, style='Dialog.TButton'); cancel_button.pack(side=tk.LEFT, padx=10)
        self.bind("<Return>", self.ok); self.bind("<Escape>", self.cancel); self.protocol("WM_DELETE_WINDOW", self.cancel); self.grab_set(); self.update_idletasks()
        screen_width = self.winfo_screenwidth(); screen_height = self.winfo_screenheight(); window_width = self.winfo_reqwidth(); window_height = self.winfo_reqheight()
        position_x = int((screen_width / 2) - (window_width / 2)); position_y = int((screen_height / 2) - (window_height / 2))
        self.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")
        self.wait_window(self)
    def ok(self, event=None): self.result = self.password_entry.get(); self.destroy()
    def cancel(self, event=None): self.result = None; self.destroy()

# --- Main Application Class ---
class AttendanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced Attendance System")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing) # Use custom close handler
        self.shutting_down = False # Shutdown flag

        self.style = ttk.Style(self.root)
        try:
            theme_to_use = 'clam'; # Or 'alt', 'default', 'vista' etc. depending on OS
            if theme_to_use in self.style.theme_names(): self.style.theme_use(theme_to_use); print(f"Using theme: {theme_to_use}")
            else: print(f"Theme '{theme_to_use}' not available, using default.")
        except tk.TclError as e: print(f"Warning: Theme '{theme_to_use}' failed: {e}. Using default.")

        # Configure custom styles
        self.style.configure('Blue.TButton', foreground='white', background='#007bff', font=('Arial', 10, 'bold'), padding=[10, 5, 10, 5]); self.style.map('Blue.TButton', background=[('active', '#0056b3'), ('disabled', '#cccccc')], foreground=[('disabled', '#666666')])
        self.style.configure('AccentBlue.TButton', foreground='white', background='#0d6efd', font=('Arial', 10, 'bold'), padding=[10, 5, 10, 5]); self.style.map('AccentBlue.TButton', background=[('active', '#0b5ed7'), ('disabled', '#cccccc')], foreground=[('disabled', '#666666')])
        self.style.configure('Red.TButton', foreground='white', background='#dc3545', font=('Arial', 10, 'bold'), padding=[10, 5, 10, 5]); self.style.map('Red.TButton', background=[('active', '#bb2d3b'), ('disabled', '#cccccc')], foreground=[('disabled', '#666666')])
        self.style.configure('Enroll.TFrame', background='#E6E6FA'); self.style.configure('Logs.TFrame', background='#F0F8FF'); self.style.configure('Details.TFrame', background='#FFFACD'); self.style.configure('Emotion.TFrame', background='#F5FFFA'); self.style.configure('Notify.TFrame', background='#FFE4E1'); self.style.configure('Manage.TFrame', background='#E0FFFF')

        # Initialize variables
        self.is_admin_mode = False; self.camera_active = False; self.video_thread = None; self.latest_frame = None
        self.frame_lock = threading.Lock(); self.stop_video_event = threading.Event(); self.last_log_time = {}; self.enrollment_in_progress = False; self.emp_details_list = {}
        self.emp_id_to_enroll = None; self.emp_name_to_enroll = None; self.emp_dept_to_enroll = None; self.selected_manage_emp_id = None
        self.enroll_photo_source = tk.StringVar(value="Capture"); self.uploaded_photo_path = tk.StringVar(value="")

        # Initialize systems
        print("Initializing Face Recognition..."); self.face_system = FaceRecognitionSystem()
        print("Loading known faces..."); known_face_ids, known_face_encodings = load_known_faces(); self.face_system.known_face_ids = known_face_ids; self.face_system.known_face_encodings = known_face_encodings; print(f"Loaded {len(self.face_system.known_face_ids)} faces.")

        # Create main frames
        self.main_frame = ttk.Frame(root, padding="10"); self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.top_bar = ttk.Frame(self.main_frame); self.top_bar.pack(fill=tk.X, pady=(0, 10))
        self.mode_label = ttk.Label(self.top_bar, text="Mode: Attendance", font=("Arial", 14, "bold")); self.mode_label.pack(side=tk.LEFT, padx=10)
        self.status_label = ttk.Label(self.top_bar, text="Status: Initializing...", width=60, font=("Arial", 10), foreground="blue", anchor="w", relief=tk.SUNKEN, padding=(5, 2)); self.status_label.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        self.admin_button = ttk.Button(self.top_bar, text="Admin Login", command=self.show_custom_login, style='Blue.TButton'); self.admin_button.pack(side=tk.RIGHT, padx=10)
        self.content_frame = ttk.Frame(self.main_frame); self.content_frame.pack(fill=tk.BOTH, expand=True)

        # Create views (packed later)
        self.create_attendance_view(); self.create_admin_view()

        # Show initial view and start camera
        self.show_attendance_view(); self.start_camera_thread(); self.set_status("Camera starting...", "blue")

    def create_attendance_view(self):
        self.attendance_frame = ttk.Frame(self.content_frame, padding="10")
        # Label to display video feed
        self.video_label = ttk.Label(self.attendance_frame, anchor=tk.CENTER); self.video_label.pack(pady=10, expand=True)
        self.video_label.config(text="Camera Feed Loading...", font=("Arial", 16), background="lightgrey", relief=tk.GROOVE, borderwidth=2)

    def create_admin_view(self):
        self.admin_frame = ttk.Frame(self.content_frame, padding="10")
        # Frame for admin-specific actions like reset
        admin_action_frame = ttk.Frame(self.admin_frame); admin_action_frame.pack(fill=tk.X, pady=(0, 10))
        self.reset_button = ttk.Button(admin_action_frame, text="Reset All Attendance Data", command=self.confirm_and_reset_data, style='Red.TButton'); self.reset_button.pack(side=tk.RIGHT, padx=10)
        # Notebook for different admin panels
        self.admin_notebook = ttk.Notebook(self.admin_frame)
        # Create and add tabs
        enroll_tab = ttk.Frame(self.admin_notebook, padding="15", style='Enroll.TFrame'); self.create_enrollment_tab(enroll_tab); self.admin_notebook.add(enroll_tab, text=' Enroll Employee ')
        logs_tab = ttk.Frame(self.admin_notebook, padding="15", style='Logs.TFrame'); self.create_logs_tab(logs_tab); self.admin_notebook.add(logs_tab, text=' View Logs ')
        emp_details_tab = ttk.Frame(self.admin_notebook, padding="15", style='Details.TFrame'); self.create_employee_details_tab(emp_details_tab); self.admin_notebook.add(emp_details_tab, text=' Employee Details ')
        emotion_tab = ttk.Frame(self.admin_notebook, padding="15", style='Emotion.TFrame'); self.create_emotion_analysis_tab(emotion_tab); self.admin_notebook.add(emotion_tab, text=' Emotion Analysis ')
        notify_tab = ttk.Frame(self.admin_notebook, padding="15", style='Notify.TFrame'); self.create_notification_tab(notify_tab); self.admin_notebook.add(notify_tab, text=' Notification Panel ')
        manage_tab = ttk.Frame(self.admin_notebook, padding="15", style='Manage.TFrame'); self.create_manage_employee_tab(manage_tab); self.admin_notebook.add(manage_tab, text=' Manage Employee ')
        self.admin_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5); self.admin_notebook.bind("<<NotebookTabChanged>>", self.on_admin_tab_change)

    # --- Helper methods for creating tabs ---
    def create_enrollment_tab(self, parent_tab):
        # Frame for employee details input
        input_frame = ttk.LabelFrame(parent_tab, text="Employee Details", padding="10"); input_frame.pack(fill=tk.X, pady=(0, 10)); input_frame.columnconfigure(1, weight=1)
        ttk.Label(input_frame, text="Employee ID:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W); self.enroll_id_entry = ttk.Entry(input_frame, width=40); self.enroll_id_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Label(input_frame, text="Employee Name:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W); self.enroll_name_entry = ttk.Entry(input_frame, width=40); self.enroll_name_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Label(input_frame, text="Department:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W); self.enroll_dept_entry = ttk.Entry(input_frame, width=40); self.enroll_dept_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.EW)
        # Frame for selecting photo source (Camera or Upload)
        photo_frame = ttk.LabelFrame(parent_tab, text="Photo Source", padding=10); photo_frame.pack(fill=tk.X, pady=10)
        ttk.Radiobutton(photo_frame, text="Capture from Camera", variable=self.enroll_photo_source, value="Capture", command=self.toggle_enroll_options).pack(anchor=tk.W, padx=5)
        ttk.Radiobutton(photo_frame, text="Upload from PC", variable=self.enroll_photo_source, value="Upload", command=self.toggle_enroll_options).pack(anchor=tk.W, padx=5)
        # Frame specific to file upload
        self.upload_frame = ttk.Frame(photo_frame, padding="5 0 0 20"); self.upload_frame.pack(fill=tk.X)
        self.upload_button = ttk.Button(self.upload_frame, text="Browse...", command=self.browse_photo_file, style='Blue.TButton', state=tk.DISABLED); self.upload_button.pack(side=tk.LEFT, padx=5)
        self.upload_path_label = ttk.Label(self.upload_frame, textvariable=self.uploaded_photo_path, relief=tk.SUNKEN, anchor=tk.W, width=40); self.upload_path_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        # Frame for action button and status label
        action_frame = ttk.Frame(parent_tab); action_frame.pack(fill=tk.X, pady=10)
        self.enroll_button = ttk.Button(action_frame, text="Enroll Employee", command=self.process_enrollment, style='AccentBlue.TButton'); self.enroll_button.pack(pady=5)
        self.enroll_status_label = ttk.Label(action_frame, text="", font=("Arial", 10, "italic"), anchor=tk.CENTER); self.enroll_status_label.pack(pady=5, fill=tk.X)
        # Initialize the state of the upload options
        self.toggle_enroll_options()

    def toggle_enroll_options(self):
        # Enable/disable the 'Browse' button based on the radio button selection
        if self.enroll_photo_source.get() == "Upload": self.upload_button.config(state=tk.NORMAL)
        else: self.upload_button.config(state=tk.DISABLED); self.uploaded_photo_path.set("") # Clear path if switching away from upload

    def browse_photo_file(self):
        # Open file dialog to select an image
        filepath = filedialog.askopenfilename(title="Select Employee Photo", filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp"), ("All Files", "*.*")], parent=self.root)
        if filepath:
            if os.path.exists(filepath): self.uploaded_photo_path.set(filepath); print(f"Selected photo for upload: {filepath}")
            else: messagebox.showerror("File Error", f"Selected file does not exist:\n{filepath}", parent=self.root); self.uploaded_photo_path.set("")

    def create_logs_tab(self, parent_tab):
        # Frame for filtering options
        filter_frame = ttk.LabelFrame(parent_tab, text="Filter Logs", padding="10"); filter_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(filter_frame, text="Employee ID (Optional):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W); self.filter_id_entry = ttk.Entry(filter_frame, width=15); self.filter_id_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(filter_frame, text="Start Date:").grid(row=0, column=2, padx=(15, 5), pady=5, sticky=tk.W)
        # Use DateEntry if available, otherwise standard Entry
        if CALENDAR_AVAILABLE: self.filter_start_date_entry = DateEntry(filter_frame, width=12, date_pattern='yyyy-mm-dd', maxdate=date.today())
        else: self.filter_start_date_entry = ttk.Entry(filter_frame, width=12); ttk.Label(filter_frame, text="(YYYY-MM-DD)").grid(row=1, column=3, padx=2, sticky=tk.W)
        self.filter_start_date_entry.grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)
        ttk.Label(filter_frame, text="End Date:").grid(row=0, column=4, padx=(15, 5), pady=5, sticky=tk.W)
        if CALENDAR_AVAILABLE: self.filter_end_date_entry = DateEntry(filter_frame, width=12, date_pattern='yyyy-mm-dd', maxdate=date.today()); self.filter_end_date_entry.set_date(date.today())
        else: self.filter_end_date_entry = ttk.Entry(filter_frame, width=12); ttk.Label(filter_frame, text="(YYYY-MM-DD)").grid(row=1, column=5, padx=2, sticky=tk.W)
        self.filter_end_date_entry.grid(row=0, column=5, padx=5, pady=5, sticky=tk.W)
        # Button to trigger loading logs
        self.load_logs_button = ttk.Button(filter_frame, text="Load Logs", command=self.load_and_display_logs, style='Blue.TButton')
        self.load_logs_button.grid(row=0, column=6, rowspan=2 if not CALENDAR_AVAILABLE else 1, padx=(20, 5), pady=5, sticky=tk.W+tk.S)
        # Frame for displaying logs in a Treeview
        log_display_frame = ttk.Frame(parent_tab); log_display_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        cols = ('Log ID', 'Employee ID', 'Name', 'Timestamp', 'Emotion'); self.log_tree = ttk.Treeview(log_display_frame, columns=cols, show='headings', height=15)
        # Define Treeview columns and headings
        self.log_tree.heading('Log ID', text='Log ID'); self.log_tree.column('Log ID', width=60, stretch=False, anchor=tk.E); self.log_tree.heading('Employee ID', text='Employee ID'); self.log_tree.column('Employee ID', width=100, stretch=False); self.log_tree.heading('Name', text='Name'); self.log_tree.column('Name', width=150, stretch=True); self.log_tree.heading('Timestamp', text='Timestamp'); self.log_tree.column('Timestamp', width=160, stretch=False); self.log_tree.heading('Emotion', text='Emotion'); self.log_tree.column('Emotion', width=100, stretch=False)
        # Add scrollbars
        vsb = ttk.Scrollbar(log_display_frame, orient="vertical", command=self.log_tree.yview); hsb = ttk.Scrollbar(log_display_frame, orient="horizontal", command=self.log_tree.xview)
        self.log_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set); self.log_tree.grid(row=0, column=0, sticky='nsew'); vsb.grid(row=0, column=1, sticky='ns'); hsb.grid(row=1, column=0, sticky='ew')
        log_display_frame.grid_rowconfigure(0, weight=1); log_display_frame.grid_columnconfigure(0, weight=1)
        # Configure alternating row colors
        self.log_tree.tag_configure('oddrow', background='white'); self.log_tree.tag_configure('evenrow', background='#E8E8E8')
        # Frame for export button
        export_frame = ttk.Frame(parent_tab); export_frame.pack(fill=tk.X, pady=10)
        self.export_button = ttk.Button(export_frame, text="Export Displayed Logs to CSV", command=self.export_displayed_logs, style='Blue.TButton'); self.export_button.pack()

    def create_employee_details_tab(self, parent_tab):
        # Frame for employee selection and month input
        selection_frame = ttk.Frame(parent_tab); selection_frame.pack(fill=tk.X, pady=5)
        ttk.Label(selection_frame, text="Select Employee:").pack(side=tk.LEFT, padx=5); self.emp_details_id_combo = ttk.Combobox(selection_frame, width=30, state="readonly"); self.emp_details_id_combo.pack(side=tk.LEFT, padx=5); self.emp_details_id_combo.bind("<<ComboboxSelected>>", self.load_employee_data_for_details_tab)
        ttk.Label(selection_frame, text="Select Month:").pack(side=tk.LEFT, padx=(20, 5)); self.emp_details_month_entry = ttk.Entry(selection_frame, width=10); self.emp_details_month_entry.pack(side=tk.LEFT, padx=5); self.emp_details_month_entry.insert(0, datetime.now().strftime("%Y-%m")) # Default to current month
        ttk.Button(selection_frame, text="Load Data", command=self.load_employee_data_for_details_tab, style='Blue.TButton').pack(side=tk.LEFT, padx=10)
        # Frame to display photo and attendance details
        display_frame = ttk.Frame(parent_tab); display_frame.pack(fill=tk.BOTH, expand=True, pady=10); display_frame.columnconfigure(1, weight=1); display_frame.rowconfigure(0, weight=1)
        # Frame for employee photo
        photo_frame = ttk.LabelFrame(display_frame, text="Employee Photo", padding=10); photo_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        self.emp_photo_label = tk.Label(photo_frame, text="Select Employee", anchor=tk.CENTER, background="lightgrey", relief=tk.GROOVE); self.emp_photo_label.config(width=30, height=15); self.emp_photo_label.pack(pady=10, padx=10, expand=True)
        # Frame for monthly attendance log
        data_frame = ttk.LabelFrame(display_frame, text="Monthly Attendance", padding=10); data_frame.grid(row=0, column=1, sticky='nsew'); data_frame.columnconfigure(0, weight=1); data_frame.rowconfigure(0, weight=1)
        cols_att = ('Date', 'Timestamp', 'Emotion'); self.emp_attendance_tree = ttk.Treeview(data_frame, columns=cols_att, show='headings', height=15)
        self.emp_attendance_tree.heading('Date', text='Date'); self.emp_attendance_tree.column('Date', width=100, stretch=False); self.emp_attendance_tree.heading('Timestamp', text='Full Timestamp'); self.emp_attendance_tree.column('Timestamp', width=160, stretch=False); self.emp_attendance_tree.heading('Emotion', text='Detected Emotion'); self.emp_attendance_tree.column('Emotion', width=120, stretch=True)
        vsb_att = ttk.Scrollbar(data_frame, orient="vertical", command=self.emp_attendance_tree.yview); hsb_att = ttk.Scrollbar(data_frame, orient="horizontal", command=self.emp_attendance_tree.xview)
        self.emp_attendance_tree.configure(yscrollcommand=vsb_att.set, xscrollcommand=hsb_att.set); self.emp_attendance_tree.grid(row=0, column=0, sticky='nsew'); vsb_att.grid(row=0, column=1, sticky='ns'); hsb_att.grid(row=1, column=0, sticky='ew')
        self.emp_attendance_tree.tag_configure('oddrow', background='white'); self.emp_attendance_tree.tag_configure('evenrow', background='#E8E8E8')

    def create_emotion_analysis_tab(self, parent_tab):
        # Frame to hold the Matplotlib chart
        chart_frame = ttk.LabelFrame(parent_tab, text="Overall Emotion Distribution (All Logs)", padding=10); chart_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0), padx=5)
        # Create Matplotlib figure and axes
        self.emotion_fig, self.emotion_ax = plt.subplots(figsize=(6, 5), dpi=100); self.emotion_fig.subplots_adjust(bottom=0.1, top=0.9, left=0.1, right=0.9) # Adjust layout
        # Embed the figure in the Tkinter window
        self.emotion_canvas = FigureCanvasTkAgg(self.emotion_fig, master=chart_frame); self.emotion_canvas_widget = self.emotion_canvas.get_tk_widget(); self.emotion_canvas_widget.pack(fill=tk.BOTH, expand=True)
        # Initial placeholder chart
        self.emotion_ax.set_title("Emotion Summary"); self.emotion_ax.pie([1], labels=['No Data']); self.emotion_ax.axis('equal') # Display 'No Data' initially
        # Button to refresh the analysis
        refresh_button = ttk.Button(parent_tab, text="Refresh Analysis", command=self.update_emotion_analysis, style='Blue.TButton'); refresh_button.pack(pady=15)

    def create_notification_tab(self, parent_tab):
        # Frame for the refresh button
        refresh_frame = ttk.Frame(parent_tab); refresh_frame.pack(fill=tk.X, pady=5)
        ttk.Button(refresh_frame, text="Refresh Notifications", command=self.update_notification_panel, style='Blue.TButton').pack()
        # Frame for the notification Treeview
        notify_display_frame = ttk.Frame(parent_tab); notify_display_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        cols = ('Type', 'Employee ID', 'Name', 'Details', 'Streak Start', 'Streak End'); self.notify_tree = ttk.Treeview(notify_display_frame, columns=cols, show='headings', height=20)
        # Define notification columns
        self.notify_tree.heading('Type', text='Type'); self.notify_tree.column('Type', width=130, stretch=False); self.notify_tree.heading('Employee ID', text='Emp ID'); self.notify_tree.column('Employee ID', width=90, stretch=False); self.notify_tree.heading('Name', text='Name'); self.notify_tree.column('Name', width=140, stretch=True); self.notify_tree.heading('Details', text='Details'); self.notify_tree.column('Details', width=180, stretch=True); self.notify_tree.heading('Streak Start', text='Start Date'); self.notify_tree.column('Streak Start', width=100, stretch=False, anchor=tk.CENTER); self.notify_tree.heading('Streak End', text='End Date'); self.notify_tree.column('Streak End', width=100, stretch=False, anchor=tk.CENTER)
        # Add scrollbars
        vsb = ttk.Scrollbar(notify_display_frame, orient="vertical", command=self.notify_tree.yview); hsb = ttk.Scrollbar(notify_display_frame, orient="horizontal", command=self.notify_tree.xview)
        self.notify_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set); self.notify_tree.grid(row=0, column=0, sticky='nsew'); vsb.grid(row=0, column=1, sticky='ns'); hsb.grid(row=1, column=0, sticky='ew')
        notify_display_frame.grid_rowconfigure(0, weight=1); notify_display_frame.grid_columnconfigure(0, weight=1)
        # Configure row and alert tags
        self.notify_tree.tag_configure('oddrow', background='white'); self.notify_tree.tag_configure('evenrow', background='#FFF0F5'); self.notify_tree.tag_configure('EmotionAlert', foreground='red'); self.notify_tree.tag_configure('AttendanceAlert', foreground='blue')

    def create_manage_employee_tab(self, parent_tab):
        # Main frame for this tab
        main_manage_frame = ttk.Frame(parent_tab); main_manage_frame.pack(fill=tk.BOTH, expand=True)
        # Frame for the employee list Treeview
        list_frame = ttk.LabelFrame(main_manage_frame, text="Employee List", padding=10); list_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5); list_frame.columnconfigure(0, weight=1); list_frame.rowconfigure(0, weight=1)
        cols_manage = ('Emp ID', 'Name', 'Department'); self.manage_emp_tree = ttk.Treeview(list_frame, columns=cols_manage, show='headings', height=10)
        self.manage_emp_tree.heading('Emp ID', text='Employee ID'); self.manage_emp_tree.column('Emp ID', width=100, stretch=False); self.manage_emp_tree.heading('Name', text='Name'); self.manage_emp_tree.column('Name', width=200, stretch=True); self.manage_emp_tree.heading('Department', text='Department'); self.manage_emp_tree.column('Department', width=150, stretch=True)
        vsb_manage = ttk.Scrollbar(list_frame, orient="vertical", command=self.manage_emp_tree.yview); hsb_manage = ttk.Scrollbar(list_frame, orient="horizontal", command=self.manage_emp_tree.xview)
        self.manage_emp_tree.configure(yscrollcommand=vsb_manage.set, xscrollcommand=hsb_manage.set); self.manage_emp_tree.grid(row=0, column=0, sticky='nsew'); vsb_manage.grid(row=0, column=1, sticky='ns'); hsb_manage.grid(row=1, column=0, sticky='ew')
        self.manage_emp_tree.bind('<<TreeviewSelect>>', self.on_employee_select) # Bind selection event
        ttk.Button(list_frame, text="Refresh List", command=self.load_all_employees_to_tree, style='Blue.TButton').grid(row=2, column=0, columnspan=2, pady=5)
        # Frame holding details form and photo/delete actions side-by-side
        details_actions_frame = ttk.Frame(main_manage_frame); details_actions_frame.pack(fill=tk.X, pady=10, padx=5)
        # Frame for the selected employee's details form
        details_form_frame = ttk.LabelFrame(details_actions_frame, text="Selected Employee Details", padding=10); details_form_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10)); details_form_frame.columnconfigure(1, weight=1)
        ttk.Label(details_form_frame, text="Employee ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3); self.manage_id_entry = ttk.Entry(details_form_frame, state='readonly', width=40); self.manage_id_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=3) # ID is read-only
        ttk.Label(details_form_frame, text="Name:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3); self.manage_name_entry = ttk.Entry(details_form_frame, width=40); self.manage_name_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=3)
        ttk.Label(details_form_frame, text="Department:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=3); self.manage_dept_entry = ttk.Entry(details_form_frame, width=40); self.manage_dept_entry.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=3)
        ttk.Button(details_form_frame, text="Save Changes", command=self.save_employee_changes, style='Blue.TButton').grid(row=3, column=0, pady=10, padx=5)
        ttk.Button(details_form_frame, text="Update Photo", command=self.prompt_update_employee_photo, style='Blue.TButton').grid(row=3, column=1, pady=10, padx=5, sticky=tk.W)
        # Frame for photo preview and delete button
        photo_delete_frame = ttk.Frame(details_actions_frame); photo_delete_frame.pack(side=tk.LEFT, padx=(10, 0))
        manage_photo_frame = ttk.LabelFrame(photo_delete_frame, text="Photo Preview", padding=5); manage_photo_frame.pack(pady=(0,10))
        self.manage_photo_label = tk.Label(manage_photo_frame, text="Select Employee", anchor=tk.CENTER, background="lightgrey", relief=tk.GROOVE, width=20, height=10); self.manage_photo_label.pack(expand=True)
        ttk.Button(photo_delete_frame, text="Delete Employee", command=self.delete_employee_action, style='Red.TButton').pack(fill=tk.X)

    # --- Tab change handler ---
    def on_admin_tab_change(self, event):
        # Refresh data when switching tabs
        try:
            if not self.admin_notebook.winfo_exists(): return # Check if notebook exists
            selected_tab_index = self.admin_notebook.index(self.admin_notebook.select())
            selected_tab_text = self.admin_notebook.tab(selected_tab_index, "text").strip() # Get text label of selected tab

            # Load data relevant to the selected tab
            if selected_tab_text == 'View Logs': self.load_and_display_logs()
            elif selected_tab_text == 'Employee Details':
                # Populate dropdown if empty, then load data for selected employee
                if not self.emp_details_id_combo.cget('values'): self.populate_employee_details_combo()
                if self.emp_details_id_combo.get(): self.load_employee_data_for_details_tab()
            elif selected_tab_text == 'Emotion Analysis': self.update_emotion_analysis()
            elif selected_tab_text == 'Notification Panel': self.update_notification_panel()
            elif selected_tab_text == 'Manage Employee': self.load_all_employees_to_tree()
        except tk.TclError as e: print(f"TclError on tab change (widget might be destroyed): {e}")
        except Exception as e: print(f"Error handling admin tab change: {e}"); import traceback; traceback.print_exc()

    # --- View Management ---
    def show_attendance_view(self):
        # Hide admin frame, show attendance frame
        self.admin_frame.pack_forget(); self.attendance_frame.pack(fill=tk.BOTH, expand=True)
        self.mode_label.config(text="Mode: Attendance"); self.admin_button.config(text="Admin Login")
        self.is_admin_mode = False
        # Ensure camera is running if not already shutting down
        if not self.camera_active and not self.stop_video_event.is_set(): self.start_camera_thread()

    def show_admin_view(self):
        # Hide attendance frame, show admin frame
        self.attendance_frame.pack_forget(); self.admin_frame.pack(fill=tk.BOTH, expand=True)
        self.mode_label.config(text="Mode: HR Administration"); self.admin_button.config(text="Exit Admin Mode")
        self.is_admin_mode = True;
        self.on_admin_tab_change(None) # Trigger data load for the initially selected admin tab

    # --- Camera Handling ---
    def start_camera_thread(self):
        # Start the video processing thread if not already active
        if self.camera_active: return; print("Starting camera thread...")
        # Create photo directory if it doesn't exist
        if not os.path.exists(EMPLOYEE_PHOTO_DIR):
            try: os.makedirs(EMPLOYEE_PHOTO_DIR); print(f"Created directory: {EMPLOYEE_PHOTO_DIR}")
            except OSError as e: print(f"Error creating directory {EMPLOYEE_PHOTO_DIR}: {e}"); self.set_status(f"Error: Cannot create {EMPLOYEE_PHOTO_DIR}", "red"); return
        # Reset stop event, create and start thread
        self.stop_video_event.clear(); self.video_thread = threading.Thread(target=self.video_loop, daemon=True); self.video_thread.start(); self.camera_active = True; self.set_status("Camera starting...", "blue")

    def video_loop(self):
        # Main loop for camera capture and processing (runs in a separate thread)
        cap = None; cam_index_tried = -1
        try:
            # Try different camera indices (0, 1, 2, -1)
            indices_to_try = [0, 1, 2, -1]; camera_found = False
            for index in indices_to_try:
                cap = None # Reset cap for each attempt
                try:
                    cap = cv2.VideoCapture(index) # Try opening camera
                    if cap is not None and cap.isOpened():
                        ret, frame_test = cap.read() # Try reading a frame
                        if ret and frame_test is not None:
                            # Success! Store index, set status, break loop
                            cam_index_tried = index; print(f"Camera opened successfully (index {cam_index_tried})."); self.set_status(f"Camera Ready (Index {cam_index_tried})", "green"); camera_found = True; break
                        else:
                            # Opened but failed read, release and try next
                            print(f"Camera index {index} opened but failed to read frame."); cap.release(); cap = None
                    else:
                         # Failed to open, release (if needed) and try next
                         print(f"Camera index {index} failed to open.");
                         if cap is not None: cap.release(); cap = None
                except Exception as e:
                    # Handle errors during probing for a specific index
                    print(f"Error during camera check for index {index}: {e}")
                    if cap is not None: # Release if open but error occurred
                        cap.release()
                        cap = None
            # If no camera found after trying all indices, raise error
            if not camera_found: raise IOError(f"Cannot open any camera (tried indices {indices_to_try}).")

            # --- Main camera loop ---
            frame_count = 0; recognition_results = [] # Store last recognition results
            while not self.stop_video_event.is_set(): # Loop until stop event is set
                ret, frame = cap.read()
                if not ret or frame is None:
                    self.set_status(f"Warning: Can't receive frame (Cam {cam_index_tried}). Check connection.", "orange"); time.sleep(0.1); continue # Skip if frame read fails

                display_frame_orig = frame.copy() # Copy frame for display modifications
                # Store the latest raw frame for enrollment capture
                with self.frame_lock: self.latest_frame = frame.copy()

                # Decide whether to perform face recognition (every few frames in non-admin mode)
                should_process = not self.is_admin_mode or self.enrollment_in_progress; # Process in attendance mode or during enrollment
                process_interval = 5; # Process every 5 frames to save resources
                process_this_frame = (frame_count % process_interval == 0)

                if should_process and process_this_frame and not self.enrollment_in_progress:
                    # Resize frame for faster recognition
                    small_frame = cv2.resize(frame, (0, 0), fx=RECOGNITION_SCALE, fy=RECOGNITION_SCALE)
                    try:
                        # Convert to RGB (face_recognition library expects RGB)
                        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                    except cv2.error as e:
                        print(f"Error converting frame to RGB: {e}. Skipping recognition for this frame."); continue # Skip if conversion fails
                    # Perform face recognition
                    recognition_results = self.face_system.recognize_faces_in_frame(rgb_small_frame)
                    # Process results (log attendance, etc.) only if in attendance mode
                    if not self.is_admin_mode:
                        self.process_recognition_results(recognition_results, frame, RECOGNITION_SCALE)

                # Draw bounding boxes and names/status on the display frame
                # Always draw if not enrolling, or draw countdown if enrolling
                if not self.is_admin_mode or self.enrollment_in_progress:
                     self.draw_on_frame(display_frame_orig, recognition_results, frame.shape[1], frame.shape[0], RECOGNITION_SCALE)

                # Resize frame for display in the Tkinter label
                display_frame_resized = cv2.resize(display_frame_orig, (CAMERA_FRAME_WIDTH, CAMERA_FRAME_HEIGHT))
                img_rgb_display = None
                try:
                    # Convert display frame back to RGB for PIL/Tkinter
                    img_rgb_display = cv2.cvtColor(display_frame_resized, cv2.COLOR_BGR2RGB)
                except Exception as conversion_err:
                    print(f"Error preparing frame for display: {conversion_err}")
                # Schedule update on the main thread if frame is valid and root window exists
                if img_rgb_display is not None and hasattr(self, 'root') and self.root.winfo_exists():
                     self.root.after(0, self.update_video_label, img_rgb_display)

                frame_count += 1; time.sleep(1 / 30) # Approx 30 FPS target (adjust as needed)

        except (IOError, cv2.error, Exception) as e:
            # Handle critical errors in the camera loop (e.g., camera disconnects)
            error_msg = f"Camera loop critical error: {e}"; self.set_status(error_msg, "red"); print(f"!!! {error_msg}"); import traceback; traceback.print_exc();
        finally:
            # Cleanup: Release camera and set flag
            if cap and cap.isOpened(): cap.release()
            self.camera_active = False; print("Camera thread finished.")
            # Clear video label on main thread if window still exists and not shutting down
            if not self.stop_video_event.is_set() and hasattr(self, 'root') and self.root.winfo_exists():
                 self.root.after(0, self.clear_video_label, "Camera Stopped")

    def process_recognition_results(self, results, original_frame, scale):
        # Process recognized faces for attendance logging
        current_time = time.time(); display_status_update = ""; status_color = "blue"
        for employee_id, _, (top, right, bottom, left) in results:
             if employee_id and employee_id != "Unknown":
                   emp_name = get_employee_name(employee_id) # Get name from DB
                   # Check if cooldown period has passed since last log attempt for this employee
                   if employee_id not in self.last_log_time or (current_time - self.last_log_time[employee_id]) > LOG_COOLDOWN_SECONDS:
                        # Attempt to log attendance and detect emotion
                        logged, emotion_str = self.log_attendance_with_emotion(employee_id, original_frame, top, bottom, left, right, scale)
                        if logged:
                            # Successfully logged
                            self.last_log_time[employee_id] = current_time # Update last log time
                            display_status_update = f"Welcome {emp_name}! Attendance marked ({emotion_str})."; status_color = "green"
                        else:
                            # Log failed (likely already logged today), still update cooldown timer
                            self.last_log_time[employee_id] = current_time;
                            # Optional: Update status about already being logged in?
                            # display_status_update = f"{emp_name} already logged today."; status_color = "orange"
        # Update the main status bar if there's a message
        if display_status_update: self.set_status(display_status_update, status_color)

    def log_attendance_with_emotion(self, employee_id, original_frame, top, bottom, left, right, scale):
        # Log attendance for an employee and detect their emotion
        emotion_str = "N/A"; logged = False
        try:
            # Calculate original coordinates from scaled recognition results
            orig_top=int(top/scale); orig_right=int(right/scale); orig_bottom=int(bottom/scale); orig_left=int(left/scale)
            # Add padding around the face for better emotion detection
            h, w, _ = original_frame.shape; padding = 15
            # Ensure padded coordinates stay within frame boundaries
            orig_top=max(0, orig_top-padding); orig_left=max(0, orig_left-padding); orig_bottom=min(h, orig_bottom+padding); orig_right=min(w, orig_right+padding)

            if orig_bottom > orig_top and orig_right > orig_left: # Check if crop dimensions are valid
                face_crop = original_frame[orig_top:orig_bottom, orig_left:orig_right]
                # Detect emotion using the emotion engine
                emotion = detect_emotion_from_face(face_crop)
                if emotion: emotion_str = emotion.capitalize()
                else: emotion_str = "Undetected" # Handle case where detection fails
            else: print(f"Warning: Invalid face crop dimensions for {employee_id}"); emotion_str = "Crop Error"

            # Attempt to log attendance (data_manager handles check for existing log today)
            if emotion_str != "Crop Error": logged = log_attendance(employee_id, emotion_str)
            else: logged = False # Don't log if cropping failed

            return logged, emotion_str # Return success status and emotion string
        except cv2.error as cv_err: print(f"OpenCV Error during face cropping for emotion: {cv_err}"); return False, "Crop Error"
        except Exception as e: print(f"Error processing emotion/log for {employee_id}: {e}"); return False, "Processing Error"

    def draw_on_frame(self, display_frame, results, orig_w, orig_h, scale):
        # Draw bounding boxes, names, and enrollment countdown on the frame
        display_h, display_w, _ = display_frame.shape

        # Display countdown if enrollment is in progress
        if self.enrollment_in_progress and hasattr(self, 'enroll_countdown_value') and self.enroll_countdown_value > 0:
             countdown_text = f"CAPTURE IN: {self.enroll_countdown_value}";
             # Calculate text size to center it
             (w, h), _ = cv2.getTextSize(countdown_text, cv2.FONT_HERSHEY_TRIPLEX, 1.5, 3)
             text_x = (display_w - w) // 2; text_y = (display_h + h) // 2
             # Draw background rectangle and text
             cv2.rectangle(display_frame, (text_x - 20, text_y - h - 20), (text_x + w + 20, text_y + 20), (0, 0, 0), cv2.FILLED, lineType=cv2.LINE_AA)
             cv2.putText(display_frame, countdown_text, (text_x, text_y), cv2.FONT_HERSHEY_TRIPLEX, 1.5, (0, 255, 255), 3, lineType=cv2.LINE_AA)

        # Draw bounding boxes and names if not enrolling
        if not self.enrollment_in_progress:
            for employee_id, _, (top, right, bottom, left) in results:
                # Scale coordinates from recognition frame size to display frame size
                rec_frame_h = orig_h * scale; rec_frame_w = orig_w * scale;
                scale_x = display_w / rec_frame_w; scale_y = display_h / rec_frame_h
                disp_top=int(top*scale_y); disp_right=int(right*scale_x); disp_bottom=int(bottom*scale_y); disp_left=int(left*scale_x)

                # Determine name and box color
                display_name = "Unknown"; color = (0, 0, 255) # Red for Unknown
                if employee_id and employee_id != "Unknown":
                    display_name = get_employee_name(employee_id)
                    # Check if recently logged
                    is_logged_recently = employee_id in self.last_log_time and (time.time() - self.last_log_time[employee_id]) <= LOG_COOLDOWN_SECONDS
                    color = (0, 255, 0) if is_logged_recently else (255, 150, 0) # Green if recent, Orange otherwise

                # Draw bounding box
                cv2.rectangle(display_frame, (disp_left, disp_top), (disp_right, disp_bottom), color, 2)
                # Draw label with name below the box
                label_y = disp_bottom + 25 # Position below box
                try:
                    # Calculate text size for background rectangle
                    (w, h), _ = cv2.getTextSize(display_name, cv2.FONT_HERSHEY_DUPLEX, 0.6, 1)
                    # Ensure background rectangle stays within frame bounds
                    label_bg_y1 = min(max(disp_bottom + 5, h + 5), display_h - 5); label_bg_y2 = min(label_bg_y1 + h + 6, display_h - 1)
                    # Draw filled background rectangle and text
                    cv2.rectangle(display_frame, (disp_left, label_bg_y1) , (min(disp_left + w + 6, display_w -1), label_bg_y2), color, cv2.FILLED)
                    cv2.putText(display_frame, display_name, (disp_left + 3, label_bg_y2 - 3), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1, lineType=cv2.LINE_AA) # White text
                except cv2.error as e: print(f"Warning: OpenCV error drawing text '{display_name}': {e}")
                except Exception as e: print(f"Warning: Generic error drawing text '{display_name}': {e}")

    def update_video_label(self, img_rgb):
        # Update the video label on the main Tkinter thread
        if self.shutting_down: return # Don't update if shutting down
        if not hasattr(self, 'root') or not self.root.winfo_exists(): return # Check if root window exists
        if hasattr(self, 'video_label') and self.video_label.winfo_exists(): # Check if video label exists
            try:
                 # Convert NumPy array to PIL image, then to Tkinter PhotoImage
                 img_pil = Image.fromarray(img_rgb); img_tk = ImageTk.PhotoImage(image=img_pil)
                 # Keep a reference to the image to prevent garbage collection
                 self.video_label.imgtk = img_tk;
                 # Update the label's image and clear any placeholder text
                 self.video_label.config(image=img_tk, text="")
            except tk.TclError: pass # Ignore errors if widget is destroyed between check and config
            except Exception as e: print(f"Error updating video label (main thread): {e}")

    def clear_video_label(self, text="Camera Off"):
        # Clear the video label (e.g., when camera stops)
        def _clear(): # Inner function to run on main thread
            if self.shutting_down: return # Don't update if shutting down
            if not hasattr(self, 'video_label') or not self.video_label.winfo_exists(): return # Check if label exists
            try:
                 # Clear image, set text, reset background/relief
                 self.video_label.config(image='', text=text, background="lightgrey", relief=tk.GROOVE);
                 self.video_label.imgtk = None # Remove reference
            except tk.TclError: pass # Ignore errors if widget destroyed
        # Schedule the clear operation on the main thread
        if hasattr(self, 'root') and self.root.winfo_exists(): self.root.after(0, _clear)

    # --- Admin Actions ---
    def show_custom_login(self):
        # Show admin login dialog or switch back to attendance mode
        if self.is_admin_mode:
            self.toggle_admin_mode(); return # If already admin, toggle back
        # Show login dialog
        dialog = AdminLoginDialog(self.root); password = dialog.result
        if password is not None: # Check if login wasn't cancelled
            if verify_admin_password(password): # Verify password using admin_logic
                self.set_status("Admin login successful.", "green"); self.show_admin_view() # Switch to admin view on success
            else:
                # Show error on failure
                messagebox.showerror("Login Failed", "Incorrect Admin Password.", parent=self.root); self.set_status("Admin login failed.", "red")
        else:
            # Login dialog was cancelled
            self.set_status("Admin login cancelled.", "orange")

    def toggle_admin_mode(self):
        # Switch between admin and attendance modes
        if self.is_admin_mode:
             # Switch back to attendance mode
             self.show_attendance_view(); self.set_status("Switched to Attendance Mode.", "blue"); self.admin_button.config(text="Admin Login")
        # Note: Switching *to* admin mode is handled by show_custom_login -> show_admin_view

    def confirm_and_reset_data(self):
        # Ask for confirmation before resetting attendance/emotion data
        confirm = messagebox.askyesno("Confirm Data Reset", "WARNING: Delete ALL attendance/emotion records?\nEmployee profiles WILL remain.\n\nThis action cannot be undone. Proceed?", icon='warning', parent=self.admin_frame)
        if confirm:
            self.set_status("Resetting data...", "orange"); self.root.update_idletasks(); print("Data reset confirmed by user...")
            # Call the reset function from admin_logic
            success = reset_attendance_emotion_data()
            if success:
                self.set_status("Attendance/emotion data reset successfully.", "green"); messagebox.showinfo("Reset Complete", "All attendance and emotion records have been deleted.", parent=self.admin_frame)
                # Refresh relevant admin tabs after reset
                if hasattr(self, 'log_tree') and self.log_tree.winfo_exists(): self.load_and_display_logs()
                if hasattr(self, 'emotion_ax') and self.emotion_ax.figure.canvas.get_tk_widget().winfo_exists(): self.update_emotion_analysis()
                if hasattr(self, 'notify_tree') and self.notify_tree.winfo_exists(): self.update_notification_panel()
                # Refresh employee details tab if currently active (as attendance logs are gone)
                try:
                    if self.admin_notebook.winfo_exists() and self.admin_notebook.index("current") == 2: # Index 2 is 'Employee Details'
                         if hasattr(self, 'emp_details_id_combo') and self.emp_details_id_combo.winfo_exists(): self.load_employee_data_for_details_tab()
                except tk.TclError: pass # Ignore if notebook/tab doesn't exist
            else:
                # Reset failed
                self.set_status("Data reset failed. Check console for details.", "red"); messagebox.showerror("Reset Failed", "Could not reset attendance/emotion data. See console output.", parent=self.admin_frame)
        else:
            # Reset cancelled by user
            self.set_status("Data reset cancelled.", "blue"); print("Data reset cancelled by user.")

    def update_notification_panel(self):
        # Refresh the notification panel with latest streak analysis
        if not hasattr(self, 'notify_tree') or not self.notify_tree.winfo_exists(): return # Check if tree exists
        self.set_status("Analyzing notifications...", "blue"); self.notify_tree.config(cursor="watch"); self.root.update_idletasks() # Show busy cursor
        # Clear existing notifications
        for item in self.notify_tree.get_children(): self.notify_tree.delete(item)
        try:
            # Get analysis results from admin_logic
            results = analyze_notification_data(days_threshold=NOTIFICATION_EMOTION_THRESHOLD, attendance_threshold=NOTIFICATION_ATTENDANCE_THRESHOLD)
            neg_streaks = results.get("negative_emotion_streaks", []); att_streaks = results.get("attendance_streaks", [])
            # Populate tree with negative emotion streaks
            for i, (eid, nm, emo, days, start_dt, end_dt) in enumerate(neg_streaks):
                tag = 'evenrow' if i % 2 == 0 else 'oddrow'; details = f"{emo} for {days} consecutive days";
                self.notify_tree.insert('', tk.END, values=('Emotion Streak', eid, nm, details, start_dt, end_dt), tags=(tag, 'EmotionAlert'))
            # Populate tree with attendance streaks
            offset = len(neg_streaks) # Offset index for alternating row colors
            for i, (eid, nm, days, start_dt, end_dt) in enumerate(att_streaks):
                 tag = 'evenrow' if (i + offset) % 2 == 0 else 'oddrow'; details = f"Attended for {days} consecutive days";
                 self.notify_tree.insert('', tk.END, values=('Attendance Streak', eid, nm, details, start_dt, end_dt), tags=(tag, 'AttendanceAlert'))
            # Update status
            total = len(neg_streaks) + len(att_streaks); self.set_status(f"Notifications updated ({total} alerts found).", "green" if total > 0 else "blue")
        except Exception as e:
             # Handle errors during analysis or display
             self.set_status("Error updating notifications panel.", "red"); messagebox.showerror("Notification Error", f"Failed to update notifications: {e}", parent=self.notify_tree); print(f"Error updating notifications: {e}"); import traceback; traceback.print_exc()
        finally:
             # Reset cursor
             if hasattr(self, 'notify_tree') and self.notify_tree.winfo_exists(): self.notify_tree.config(cursor="")

    # --- Enrollment ---
    def process_enrollment(self):
        # Start the enrollment process based on user input
        emp_id = self.enroll_id_entry.get().strip(); emp_name = self.enroll_name_entry.get().strip(); emp_dept = self.enroll_dept_entry.get().strip()
        # Validate input
        if not emp_id or not emp_name: messagebox.showerror("Input Error", "Employee ID and Name are required.", parent=self.root); return
        # Check if employee ID already exists
        try:
            conn = sqlite3.connect(DATABASE_FILE); cursor = conn.cursor(); cursor.execute("SELECT 1 FROM employees WHERE employee_id = ?", (emp_id,)); exists = cursor.fetchone(); conn.close()
            if exists: messagebox.showerror("ID Exists", f"Employee ID '{emp_id}' already exists in the database.", parent=self.root); return
        except sqlite3.Error as e: messagebox.showerror("Database Error", f"Error checking employee ID: {e}", parent=self.root); return

        # Proceed based on selected photo source
        source = self.enroll_photo_source.get()
        if source == "Capture":
             # Start camera capture sequence
             self.initiate_camera_enrollment(emp_id, emp_name, emp_dept)
        elif source == "Upload":
             # Use uploaded file
             image_path = self.uploaded_photo_path.get()
             if not image_path or not os.path.exists(image_path): messagebox.showerror("Input Error", "Please select a valid image file to upload.", parent=self.root); return
             # Enroll using the selected file
             self.enroll_with_file(emp_id, emp_name, emp_dept, image_path, is_upload=True)
        else: messagebox.showerror("Error", "Invalid photo source selected.", parent=self.root)

    def initiate_camera_enrollment(self, emp_id, emp_name, emp_dept):
        # Prepare for capturing an enrollment photo from the camera
        if self.enrollment_in_progress: print("Enrollment already in progress."); return # Prevent multiple enrollments at once
        self.emp_id_to_enroll = emp_id; self.emp_name_to_enroll = emp_name; self.emp_dept_to_enroll = emp_dept
        # Check if camera is ready
        with self.frame_lock: frame_available = self.latest_frame is not None
        if not self.camera_active or not frame_available: messagebox.showerror("Camera Error", "Camera not ready for capture.", parent=self.root); return
        # Start countdown
        self.enrollment_in_progress = True; self.enroll_button.config(state=tk.DISABLED); # Disable enroll button
        self.enroll_status_label.config(text=f"Get Ready! Look at the camera...", foreground="blue"); self.set_status(f"Starting enrollment capture for {self.emp_name_to_enroll}...", "blue");
        self.enrollment_countdown(ENROLL_COUNTDOWN_SECONDS) # Start the timer

    def enrollment_countdown(self, count):
        # Recursive function for the enrollment countdown timer
        if count > 0:
            if not self.enrollment_in_progress: return # Stop if cancelled somehow
            self.enroll_countdown_value = count; self.enroll_status_label.config(text=f"Capturing in {count}...")
            # Schedule next countdown step after 1 second
            self.root.after(1000, self.enrollment_countdown, count - 1)
        else:
            # Countdown finished, capture frame if still in progress
            if self.enrollment_in_progress:
                self.enroll_countdown_value = 0; self.enroll_status_label.config(text="Capturing frame..."); self.root.update_idletasks(); # Update label immediately
                self.capture_frame_and_enroll()

    def capture_frame_and_enroll(self):
        # Capture the current frame from the camera thread and save it for enrollment
        if not self.enrollment_in_progress: return # Check if still enrolling
        captured_frame = None
        try:
            # Get the latest frame safely using the lock
            with self.frame_lock:
                if self.latest_frame is not None: captured_frame = self.latest_frame.copy()
                else: raise ValueError("Could not get a valid frame from the camera thread.")
            # Create a temporary directory/file to save the captured frame
            temp_dir = "temp_enroll"; os.makedirs(temp_dir, exist_ok=True);
            # Create a safe filename
            safe_id_part = "".join(c if c.isalnum() else "_" for c in self.emp_id_to_enroll); timestamp = int(time.time());
            temp_image_path = os.path.join(temp_dir, f"{safe_id_part}_enroll_{timestamp}.jpg")
            # Save the frame as a JPEG image
            save_success = cv2.imwrite(temp_image_path, captured_frame)
            if not save_success: raise IOError(f"Failed to save temporary enrollment image to {temp_image_path}")
            print(f"Enrollment frame saved temporarily to {temp_image_path}")
            # Enroll using the saved temporary file
            self.enroll_with_file(self.emp_id_to_enroll, self.emp_name_to_enroll, self.emp_dept_to_enroll, temp_image_path, is_upload=False)
            # Clean up the temporary file
            try: os.remove(temp_image_path); print(f"Deleted temporary file: {temp_image_path}")
            except OSError as e: print(f"Warning: Could not delete temporary enrollment file {temp_image_path}: {e}")
        except (ValueError, IOError, Exception) as e:
             # Handle errors during capture or saving
             error_msg = f"Error during frame capture/saving: {e}"; print(f"!!! {error_msg}"); messagebox.showerror("Capture Error", error_msg, parent=self.root);
             self.enroll_status_label.config(text="Capture Failed!", foreground="red"); self.set_status("Enrollment capture failed.", "red")
        finally:
             # Reset enrollment state regardless of success/failure
             self.enrollment_in_progress = False
             # Re-enable enroll button if it exists
             if hasattr(self, 'enroll_button') and self.enroll_button.winfo_exists(): self.enroll_button.config(state=tk.NORMAL)


    def enroll_with_file(self, emp_id, emp_name, emp_dept, image_path, is_upload=False):
        # Enroll employee using a provided image file path (either uploaded or temporarily saved)
        success = False
        try:
            # Update status labels
            self.enroll_status_label.config(text=f"Processing face from file...", foreground='orange'); self.set_status(f"Processing face for {emp_name}...", "blue"); self.root.update_idletasks()
            # Call add_employee from data_manager
            success = add_employee(emp_id, emp_name, image_path, emp_dept)

            if success:
                # Enrollment successful
                self.enroll_status_label.config(text=f"Enrollment Successful!", foreground="green"); self.set_status(f"Employee {emp_name} enrolled.", "green"); messagebox.showinfo("Enrollment Success", f"Employee '{emp_name}' (ID: {emp_id}) enrolled successfully!", parent=self.root)
                # Copy the enrollment photo to the permanent employee_photos directory
                photo_dest_path = self.get_employee_photo_path(emp_id, find_existing=False)
                if photo_dest_path:
                     try: shutil.copy(image_path, photo_dest_path); print(f"Saved enrollment photo to: {photo_dest_path}")
                     except Exception as copy_err:
                          print(f"Warning: Failed to copy photo to {photo_dest_path}: {copy_err}");
                          messagebox.showwarning("Photo Copy Warning", f"Enrollment successful, but failed to save photo to employee directory.\nPlease manually add '{os.path.basename(photo_dest_path)}' to the '{EMPLOYEE_PHOTO_DIR}' folder if needed.", parent=self.root)
                else:
                     print(f"Warning: Could not determine destination photo path for employee {emp_id}");
                     messagebox.showwarning("Photo Path Warning", f"Enrollment successful, but could not determine photo save path.\nPlease manually add photo to the '{EMPLOYEE_PHOTO_DIR}' folder if needed.", parent=self.root)

                # Reload known faces into the face recognition system
                print("Reloading known faces after enrollment..."); ids, encodings = load_known_faces(); self.face_system.known_face_ids = ids; self.face_system.known_face_encodings = encodings; print(f"Reloaded {len(ids)} faces.")
                # Clear enrollment form fields
                self.enroll_id_entry.delete(0, tk.END); self.enroll_name_entry.delete(0, tk.END); self.enroll_dept_entry.delete(0, tk.END)
                self.uploaded_photo_path.set("") # Clear uploaded file path
            else:
                 # Enrollment failed (e.g., no face found, DB error reported by add_employee)
                 enroll_fail_msg = f"Failed to enroll {emp_name}.\nPlease check the console output for more details (e.g., 'No face found', 'DB Error').";
                 self.enroll_status_label.config(text=f"Enrollment Failed.", foreground="red"); self.set_status(f"Enrollment failed for {emp_name}.", "red"); messagebox.showerror("Enrollment Failed", enroll_fail_msg, parent=self.root)
        except (sqlite3.Error, Exception) as e:
             # Handle unexpected errors during the enrollment process
             error_msg = f"Unexpected error during enrollment processing: {e}"; self.enroll_status_label.config(text="Enrollment Error!", foreground="red"); self.set_status("Enrollment processing error.", "red"); messagebox.showerror("Enrollment Error", error_msg, parent=self.root); print(f"!!! {error_msg}"); import traceback; traceback.print_exc(); success = False
        finally:
             # Reset enrollment flags and UI elements
             self.enrollment_in_progress = False; self.enroll_countdown_value = 0
             try:
                 # Re-enable enroll button if it exists
                 if hasattr(self,'enroll_button') and self.enroll_button.winfo_exists(): self.enroll_button.config(state=tk.NORMAL)
                 # Clear status label only if enrollment failed, otherwise keep success message
                 if hasattr(self,'enroll_status_label') and self.enroll_status_label.winfo_exists() and not success:
                      self.enroll_status_label.config(text="")
             except tk.TclError: pass # Ignore if widgets destroyed


    # --- Log Loading & Export ---
    def load_and_display_logs(self):
        # Load attendance logs based on filter criteria and display in Treeview
        if not hasattr(self, 'log_tree') or not self.log_tree.winfo_exists(): return # Check if tree exists
        emp_id = self.filter_id_entry.get().strip() or None; start_date_str = None; end_date_str = None
        # Get and validate dates from filter widgets
        try:
            if CALENDAR_AVAILABLE:
                 # Get dates from tkcalendar DateEntry widgets
                 start_date_obj=self.filter_start_date_entry.get_date(); end_date_obj=self.filter_end_date_entry.get_date();
                 start_date_str=start_date_obj.strftime('%Y-%m-%d'); end_date_str=end_date_obj.strftime('%Y-%m-%d')
            else:
                 # Get dates from standard Entry widgets
                 start_date_str = self.filter_start_date_entry.get().strip() or None; end_date_str = self.filter_end_date_entry.get().strip() or None
                 # Basic format validation for manual entry
                 if start_date_str and len(start_date_str) != 10: raise ValueError("Invalid start date format (YYYY-MM-DD)")
                 if end_date_str and len(end_date_str) != 10: raise ValueError("Invalid end date format (YYYY-MM-DD)")
            # Check if start date is after end date
            if start_date_str and end_date_str and start_date_str > end_date_str:
                 messagebox.showwarning("Date Warning", "Start date is after end date. Results might be empty.", parent=self.root)
        except Exception as e: messagebox.showerror("Date Error", f"Invalid date input: {e}", parent=self.root); return

        # Disable load button, set status, clear tree
        self.load_logs_button.config(state=tk.DISABLED); self.set_status("Loading logs...", "blue")
        for item in self.log_tree.get_children(): self.log_tree.delete(item); self.root.update_idletasks() # Clear tree immediately

        # --- Fetch logs in background (using 'after' to avoid blocking GUI) ---
        def fetch_logs_task():
            try:
                 # Call admin_logic function to get logs from DB
                 logs = get_attendance_logs(start_date_str=start_date_str, end_date_str=end_date_str, employee_id=emp_id)
                 # Schedule update of Treeview on main thread
                 self.root.after(0, self.update_log_treeview, logs)
            except Exception as e:
                 # Handle errors during log fetching
                 error_msg = f"Failed to load logs: {e}"; print(f"Error: {error_msg}");
                 # Show error message and update status on main thread
                 self.root.after(0, lambda: messagebox.showerror("Load Error", error_msg, parent=self.root))
                 self.root.after(0, self.set_status, "Error loading logs.", "red")
            finally:
                 # Re-enable load button on main thread when done
                 if hasattr(self, 'load_logs_button') and self.load_logs_button.winfo_exists():
                      self.root.after(0, lambda: self.load_logs_button.config(state=tk.NORMAL))
        # Schedule the background task to run shortly after current event processing
        self.root.after(10, fetch_logs_task)

    def update_log_treeview(self, logs):
        # Populate the log Treeview with fetched data (runs on main thread)
        try:
             if not self.log_tree.winfo_exists(): return # Check if tree still exists
             # Clear tree again just in case (though already cleared in load_and_display_logs)
             for item in self.log_tree.get_children(): self.log_tree.delete(item)
             # Insert fetched logs into the tree
             for i, log_entry in enumerate(logs):
                 tag = 'evenrow' if i % 2 == 0 else 'oddrow' # Apply alternating row tag
                 # Ensure data matches expected columns
                 if len(log_entry) == len(self.log_tree['columns']):
                      self.log_tree.insert('', tk.END, values=log_entry, tags=(tag,))
                 else: print(f"Warning: Mismatched log data columns: Expected {len(self.log_tree['columns'])}, got {len(log_entry)} for {log_entry}")
             # Update status message
             log_count = len(logs); status_msg = f"Loaded {log_count} log entr{'y' if log_count == 1 else 'ies'}."; self.set_status(status_msg, "green" if log_count > 0 else "blue")
        except tk.TclError as e: print(f"TclError updating log treeview (widget might be destroyed): {e}")
        except Exception as e: print(f"Error updating log treeview: {e}"); self.set_status("Error displaying logs.", "red")

    def export_displayed_logs(self):
        # Export the currently displayed logs in the Treeview to a CSV file
        displayed_logs = [];
        try:
             # Check if tree exists
             if not self.log_tree.winfo_exists(): return
             # Get all data rows currently in the treeview
             for item_id in self.log_tree.get_children():
                  item_values = self.log_tree.item(item_id)['values']; displayed_logs.append(item_values)
        except Exception as e: messagebox.showerror("Export Error", f"Failed to retrieve data from log table: {e}", parent=self.root); return

        if not displayed_logs: messagebox.showinfo("Export Info", "No logs are currently displayed to export.", parent=self.root); return

        # Ask user for save file path
        try: filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")], title="Save Logs As...", initialfile=f"attendance_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", parent=self.root)
        except Exception as e: messagebox.showerror("File Dialog Error", f"Failed to open save dialog: {e}", parent=self.root); return

        if not filepath: self.set_status("Export cancelled.", "orange"); return # User cancelled save dialog

        # Export data using admin_logic function
        self.set_status(f"Exporting logs to {os.path.basename(filepath)}...", "blue"); self.root.update_idletasks()
        success = export_logs_to_csv(filepath, displayed_logs)
        if success: messagebox.showinfo("Export Successful", f"Logs successfully exported to:\n{filepath}", parent=self.root); self.set_status(f"Logs exported successfully.", "green")
        else: messagebox.showerror("Export Failed", "Failed to export logs. Check console output.", parent=self.root); self.set_status(f"Export failed.", "red")

    # --- Manage Employee Tab Handlers ---
    def load_all_employees_to_tree(self):
        # Load all employee data into the 'Manage Employee' Treeview
        if not hasattr(self, 'manage_emp_tree') or not self.manage_emp_tree.winfo_exists(): return # Check if tree exists
        print("Loading employees into Manage tab treeview...")
        try:
            # Clear existing tree items
            for item in self.manage_emp_tree.get_children(): self.manage_emp_tree.delete(item)
            # Get all employees from data_manager
            employees = get_all_employees()
            # Populate tree
            for i, emp_data in enumerate(employees):
                 tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                 # Expecting (id, name, department)
                 if len(emp_data) >= 3:
                      emp_id, name, dept = emp_data[:3];
                      self.manage_emp_tree.insert('', tk.END, values=(str(emp_id), name, dept or ''), tags=(tag,)) # Ensure ID is string, handle None dept
                 else: print(f"Warning: Skipping employee data with unexpected format: {emp_data}")
            print(f"Loaded {len(employees)} employees into manage tree.")
            self.clear_manage_details_fields() # Clear details form after refresh
        except Exception as e: messagebox.showerror("Load Error", f"Failed to load employee list for management tab: {e}", parent=self.root); print(f"Error loading employee list for manage tab: {e}")

    def clear_manage_details_fields(self):
        # Clear the input fields and photo preview in the 'Manage Employee' tab
        self.selected_manage_emp_id = None # Reset selected ID
        # Clear entry fields safely, checking if they exist
        if hasattr(self,'manage_id_entry') and self.manage_id_entry.winfo_exists(): self.manage_id_entry.config(state='normal'); self.manage_id_entry.delete(0, tk.END); self.manage_id_entry.config(state='readonly')
        if hasattr(self,'manage_name_entry') and self.manage_name_entry.winfo_exists(): self.manage_name_entry.delete(0, tk.END)
        if hasattr(self,'manage_dept_entry') and self.manage_dept_entry.winfo_exists(): self.manage_dept_entry.delete(0, tk.END)
        # Clear photo preview safely
        if hasattr(self,'manage_photo_label') and self.manage_photo_label.winfo_exists():
             self.manage_photo_label.config(image='', text="Select Employee"); self.manage_photo_label.imgtk = None

    def on_employee_select(self, event=None):
        # Handle selection change in the 'Manage Employee' Treeview
        try:
            if not hasattr(self, 'manage_emp_tree') or not self.manage_emp_tree.winfo_exists(): return # Check tree exists
            selected_item = self.manage_emp_tree.focus() # Get the ID of the selected item
            if not selected_item: self.clear_manage_details_fields(); return # Clear form if selection cleared
            # Get data associated with the selected item
            item_data = self.manage_emp_tree.item(selected_item); values = item_data['values']
            # Validate data format
            if not values or len(values) < 3: print("Warning: Selected item has invalid data."); self.clear_manage_details_fields(); return
            # Extract data (ensure ID is stored as string)
            emp_id, name, dept = str(values[0]), values[1], values[2]; self.selected_manage_emp_id = emp_id
            # Populate the details form fields, checking if widgets exist
            if hasattr(self, 'manage_id_entry') and self.manage_id_entry.winfo_exists(): self.manage_id_entry.config(state='normal'); self.manage_id_entry.delete(0, tk.END); self.manage_id_entry.insert(0, emp_id); self.manage_id_entry.config(state='readonly')
            if hasattr(self, 'manage_name_entry') and self.manage_name_entry.winfo_exists(): self.manage_name_entry.delete(0, tk.END); self.manage_name_entry.insert(0, name)
            if hasattr(self, 'manage_dept_entry') and self.manage_dept_entry.winfo_exists(): self.manage_dept_entry.delete(0, tk.END); self.manage_dept_entry.insert(0, dept or '') # Handle None dept
            # Display the employee's photo preview
            self.display_manage_employee_photo(emp_id)
        except Exception as e: print(f"Error handling employee selection in manage tab: {e}"); messagebox.showerror("Selection Error", f"Could not display selected employee details: {e}", parent=self.root); self.clear_manage_details_fields()

    def display_manage_employee_photo(self, employee_id):
        # Display the photo preview for the selected employee in the 'Manage' tab
         employee_id_str = str(employee_id) # Ensure ID is string
         if not hasattr(self, 'manage_photo_label') or not self.manage_photo_label.winfo_exists(): return # Check label exists
         # Get the photo path using the helper function
         photo_path = self.get_employee_photo_path(employee_id_str)
         img_tk = None # Placeholder for PhotoImage object
         if photo_path and os.path.exists(photo_path):
             # If photo exists, load, resize, and display it
             try:
                 img = Image.open(photo_path); img.thumbnail((150, 150), Image.Resampling.LANCZOS); # Resize using LANCZOS
                 img_tk = ImageTk.PhotoImage(img)
                 # Update label with image, clear text, adjust size
                 self.manage_photo_label.config(image=img_tk, text="", width=img_tk.width(), height=img_tk.height());
                 self.manage_photo_label.imgtk = img_tk # Keep reference
             except Exception as e:
                 # Handle errors loading/processing the image
                 print(f"Error loading preview photo {photo_path}: {e}");
                 self.manage_photo_label.config(image="", text="Error", width=20, height=10); self.manage_photo_label.imgtk = None
         else:
             # If no photo found, display placeholder text
             self.manage_photo_label.config(image="", text="No Photo", width=20, height=10); self.manage_photo_label.imgtk = None

    def save_employee_changes(self):
        # Save changes made to the selected employee's details
        if self.selected_manage_emp_id is None: messagebox.showwarning("Selection Error", "Please select an employee from the list first.", parent=self.root); return
        # Get new details from entry fields
        new_name = self.manage_name_entry.get().strip(); new_dept = self.manage_dept_entry.get().strip()
        # Validate input
        if not new_name: messagebox.showerror("Input Error", "Employee Name cannot be empty.", parent=self.root); return
        # Call update function from data_manager
        try:
            success = update_employee_details(self.selected_manage_emp_id, new_name, new_dept)
            if success:
                 messagebox.showinfo("Update Successful", f"Details for employee {self.selected_manage_emp_id} updated successfully.", parent=self.root);
                 self.load_all_employees_to_tree() # Refresh the list to show changes
            else: messagebox.showerror("Update Failed", "Could not update employee details (employee ID might not exist anymore?). Check console.", parent=self.root)
        except Exception as e: messagebox.showerror("Update Error", f"An unexpected error occurred while saving changes: {e}", parent=self.root); print(f"Error saving employee changes: {e}")

    def prompt_update_employee_photo(self):
        # Prompt user to select a new photo file and update the employee's face encoding
        if self.selected_manage_emp_id is None: messagebox.showwarning("Selection Error", "Please select an employee from the list first.", parent=self.root); return
        # Ask user for the new photo file
        filepath = filedialog.askopenfilename(title=f"Select New Photo for {self.selected_manage_emp_id}", filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")], parent=self.root)
        if not filepath: return # User cancelled

        # Confirm the update action
        confirm = messagebox.askyesno("Confirm Photo Update", f"Update the photo for employee {self.selected_manage_emp_id}?\n\nThis will re-process the face encoding using the new image.", parent=self.root)
        if not confirm: return

        # Update photo using data_manager function
        try:
            self.set_status(f"Updating photo and encoding for {self.selected_manage_emp_id}...", "blue")
            success = update_employee_photo(self.selected_manage_emp_id, filepath) # This handles encoding update
            if success:
                 messagebox.showinfo("Update Successful", f"Photo and face encoding updated successfully for employee {self.selected_manage_emp_id}.", parent=self.root); self.set_status(f"Photo updated successfully.", "green")
                 # Reload known faces for the running application
                 print("Reloading known faces after photo update..."); ids, encs = load_known_faces(); self.face_system.known_face_ids = ids; self.face_system.known_face_encodings = encs; print(f"Reloaded {len(ids)} faces.")
                 # Refresh the photo preview in the manage tab
                 self.display_manage_employee_photo(self.selected_manage_emp_id)
                 # Copy the new photo to the employee_photos directory, overwriting old one if same format
                 photo_dest_path = self.get_employee_photo_path(self.selected_manage_emp_id, find_existing=False) # Get preferred save path (e.g., .jpg)
                 if photo_dest_path:
                     try:
                         # Remove existing photo(s) first to avoid conflicts if format changes (e.g., jpg -> png)
                         self.remove_existing_employee_photos(self.selected_manage_emp_id)
                         shutil.copy(filepath, photo_dest_path); print(f"Copied new photo to {photo_dest_path}")
                     except Exception as copy_err:
                         print(f"Warning: Failed to copy updated photo to {photo_dest_path}: {copy_err}")
                         messagebox.showwarning("Photo Copy Warning", f"Photo encoding updated, but failed to save new photo file to '{EMPLOYEE_PHOTO_DIR}'. Please add it manually if needed.", parent=self.root)
            else: messagebox.showerror("Update Failed", f"Could not update photo and encoding.\nPlease check console for errors (e.g., no face found in new image).", parent=self.root); self.set_status(f"Photo update failed.", "red")
        except Exception as e: messagebox.showerror("Update Error", f"An unexpected error occurred during photo update: {e}", parent=self.root); self.set_status("Error updating photo.", "red"); print(f"Error updating employee photo: {e}")

    def remove_existing_employee_photos(self, employee_id):
        # Helper to remove existing .jpg or .png photos for an employee ID
        employee_id_str = str(employee_id)
        if not employee_id_str: return
        safe_id_str = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in employee_id_str)
        base_path = os.path.join(EMPLOYEE_PHOTO_DIR, safe_id_str)
        for ext in ['.jpg', '.png', '.jpeg', '.bmp']: # Check common extensions
            path_to_remove = base_path + ext
            if os.path.exists(path_to_remove):
                try:
                    os.remove(path_to_remove)
                    print(f"Removed existing photo: {path_to_remove}")
                except OSError as e:
                    print(f"Warning: Could not remove existing photo {path_to_remove}: {e}")


    def delete_employee_action(self):
        # Delete the selected employee and their attendance records
        if self.selected_manage_emp_id is None: messagebox.showwarning("Selection Error", "Please select an employee from the list first.", parent=self.root); return
        emp_id_to_delete = str(self.selected_manage_emp_id); # Ensure ID is string
        # Try to get the name for the confirmation dialog
        emp_name = emp_id_to_delete # Default to ID if name lookup fails
        try:
            selected_item = self.manage_emp_tree.focus(); item_data = self.manage_emp_tree.item(selected_item)
            if item_data and len(item_data['values']) > 1: emp_name = item_data['values'][1]
        except: pass # Ignore errors getting name, just use ID

        # Show strong warning confirmation dialog
        confirm = messagebox.askyesno("Confirm Deletion", f"--- WARNING! ---\n\nPermanently delete employee:\nID: {emp_id_to_delete}\nName: {emp_name}\n\nThis will also delete ALL associated attendance records!\nThis action CANNOT BE UNDONE.\n\nAre you absolutely sure you want to proceed?", icon='warning', default='no', parent=self.root)
        if confirm:
            try:
                self.set_status(f"Deleting employee {emp_id_to_delete} and their logs...", "orange")
                # Call delete function from data_manager (handles deleting logs via cascade or manually)
                success = delete_employee_data(emp_id_to_delete)
                if success:
                     messagebox.showinfo("Deletion Successful", f"Employee {emp_id_to_delete} and their attendance records have been deleted.", parent=self.root); self.set_status(f"Employee {emp_id_to_delete} deleted.", "green")
                     # Remove associated photo file(s)
                     self.remove_existing_employee_photos(emp_id_to_delete)
                     # Reload known faces for the running application
                     print("Reloading known faces after deletion..."); ids, encs = load_known_faces(); self.face_system.known_face_ids = ids; self.face_system.known_face_encodings = encs; print(f"Reloaded {len(ids)} faces.")
                     # Refresh the employee list treeview
                     self.load_all_employees_to_tree()
                else: messagebox.showerror("Deletion Failed", f"Could not delete employee {emp_id_to_delete}.\nThey may have already been deleted, or a database error occurred (Check Console).", parent=self.root); self.set_status(f"Deletion failed for {emp_id_to_delete}.", "red")
            except Exception as e: messagebox.showerror("Deletion Error", f"An unexpected error occurred during deletion: {e}", parent=self.root); self.set_status("Error during employee deletion.", "red"); print(f"Error deleting employee: {e}")
        else:
            self.set_status("Employee deletion cancelled.", "blue")

    # --- Employee Details Tab ---
    def populate_employee_details_combo(self):
        # Populate the employee dropdown in the 'Employee Details' tab
        print("Populating employee details combobox...");
        try:
            # Get list of employees (ID, Name) from DB
            conn = sqlite3.connect(DATABASE_FILE); cursor = conn.cursor(); cursor.execute("SELECT employee_id, name FROM employees ORDER BY name"); employees = cursor.fetchall(); conn.close()
            if not employees:
                 # Handle case with no employees
                 print("No employees found in database."); self.emp_details_id_combo['values'] = []; self.emp_details_id_combo.set(''); self.emp_details_list = {}; return
            # Create mapping from display name ("Name (ID)") to employee ID
            self.emp_details_list = {f"{name} ({emp_id})": emp_id for emp_id, name in employees};
            # Set values for the combobox and select the first one
            self.emp_details_id_combo['values'] = list(self.emp_details_list.keys());
            # self.emp_details_id_combo.current(0) # Select first item by default
            self.emp_details_id_combo.set('') # Or leave it blank initially
            print(f"Populated employee details combobox with {len(employees)} employees.")
        except sqlite3.Error as e: messagebox.showerror("Database Error", f"Failed to load employee list for details tab: {e}", parent=self.root); print(f"DB error loading employee list: {e}")
        except Exception as e: messagebox.showerror("Error", f"Error loading employee list for details tab: {e}", parent=self.root); print(f"Error loading employee list: {e}")

    def load_employee_data_for_details_tab(self, event=None):
        # Load and display photo and attendance logs for the selected employee and month
        selected_display_name = self.emp_details_id_combo.get()
        # Clear details if no employee is selected
        if not selected_display_name:
            if hasattr(self,'emp_photo_label') and self.emp_photo_label.winfo_exists(): self.emp_photo_label.config(image="", text="Select Employee"); self.emp_photo_label.imgtk = None
            if hasattr(self, 'emp_attendance_tree') and self.emp_attendance_tree.winfo_exists():
                 for item in self.emp_attendance_tree.get_children(): self.emp_attendance_tree.delete(item)
            return

        # Get employee ID from the selected display name
        employee_id = self.emp_details_list.get(selected_display_name)
        if not employee_id: print(f"Error: Could not map display name '{selected_display_name}' back to employee ID."); return

        # Get and validate the selected month
        month_str = self.emp_details_month_entry.get().strip()
        try:
            # Parse year and month
            year, month = map(int, month_str.split('-'));
            # Calculate start and end dates for the selected month
            start_date = f"{year:04d}-{month:02d}-01"; _, last_day = calendar.monthrange(year, month); end_date = f"{year:04d}-{month:02d}-{last_day:02d}"
        except ValueError as ve: messagebox.showerror("Input Error", f"Invalid month format '{month_str}'. Please use YYYY-MM.", parent=self.root); return
        except Exception as e: messagebox.showerror("Date Error", f"Error processing month '{month_str}': {e}", parent=self.root); return

        # --- Display Employee Photo ---
        photo_path = self.get_employee_photo_path(str(employee_id)); # Get photo path (ensure ID is string)
        img_tk = None # Placeholder for PhotoImage
        if hasattr(self,'emp_photo_label') and self.emp_photo_label.winfo_exists():
            if photo_path and os.path.exists(photo_path):
                # Load, resize, and display photo if found
                try: img = Image.open(photo_path); img.thumbnail((250, 250), Image.Resampling.LANCZOS); img_tk = ImageTk.PhotoImage(img); self.emp_photo_label.config(image=img_tk, text="", width=img_tk.width(), height=img_tk.height()); self.emp_photo_label.imgtk = img_tk # Keep reference
                except Exception as e: print(f"Error loading photo {photo_path}: {e}"); self.emp_photo_label.config(image="", text="Error Photo", width=30, height=15); self.emp_photo_label.imgtk = None
            else:
                # Display placeholder if no photo found
                self.emp_photo_label.config(image="", text="No Photo", width=30, height=15); self.emp_photo_label.imgtk = None

        # --- Load and Display Attendance Logs ---
        try:
            # Check if attendance tree exists
            if not hasattr(self, 'emp_attendance_tree') or not self.emp_attendance_tree.winfo_exists(): return
            # Clear existing logs
            for item in self.emp_attendance_tree.get_children(): self.emp_attendance_tree.delete(item)
            # Get logs for the selected employee and date range
            logs = get_attendance_logs(start_date_str=start_date, end_date_str=end_date, employee_id=str(employee_id)) # Ensure ID is string
            # Populate treeview
            if not logs:
                 # Display message if no logs found for the month
                 self.emp_attendance_tree.insert('', tk.END, values=("No attendance data", f"found for {month_str}", ""))
            else:
                 # Insert each log entry
                 for i, log_entry in enumerate(logs):
                     # log_entry format: (log_id, employee_id, name, timestamp, detected_emotion)
                     log_id, _, _, timestamp_str, emotion = log_entry; tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                     try:
                         # Format data for display (extract date from timestamp)
                         date_obj = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S'); date_str = date_obj.strftime('%Y-%m-%d')
                         tree_cols = self.emp_attendance_tree['columns']
                         # Ensure columns match before inserting
                         if len(tree_cols) == 3: # Expecting ('Date', 'Timestamp', 'Emotion')
                              self.emp_attendance_tree.insert('', tk.END, values=(date_str, timestamp_str, emotion or 'N/A'), tags=(tag,))
                         else: print(f"Warning: Employee details tree column count mismatch ({len(tree_cols)} vs 3)")
                     except ValueError: print(f"Warning: Could not parse timestamp '{timestamp_str}' for log ID {log_id}."); self.emp_attendance_tree.insert('', tk.END, values=("Parse Error", timestamp_str, emotion or 'N/A'), tags=(tag,))
                     except Exception as parse_err: print(f"Error processing log entry {log_id}: {parse_err}")
        except sqlite3.Error as db_err: messagebox.showerror("Database Error", f"Failed to load attendance logs: {db_err}", parent=self.root); print(f"DB error loading attendance for details tab: {db_err}")
        except Exception as e: messagebox.showerror("Load Error", f"Failed to load attendance data: {e}", parent=self.root); print(f"Error loading attendance for details tab: {e}"); import traceback; traceback.print_exc()

    # --- Emotion Analysis Tab ---
    def update_emotion_analysis(self):
        # Update the emotion distribution pie chart
        print("Updating emotion analysis chart..."); self.set_status("Loading analysis data...", "blue"); self.root.update_idletasks()
        try:
            # Check if chart components exist
            if not hasattr(self, 'emotion_ax') or not hasattr(self.emotion_ax,'figure') or not self.emotion_ax.figure.canvas.get_tk_widget().winfo_exists(): return
            # Get all logs from the database
            logs = get_attendance_logs()
            # Handle case with no logs
            if not logs:
                 self.set_status("No attendance data available for analysis.", "orange"); self.emotion_ax.clear(); self.emotion_ax.set_title("Emotion Summary"); self.emotion_ax.pie([1], labels=['No Data']); self.emotion_ax.axis('equal'); self.emotion_canvas.draw(); return
            # Extract and clean emotion data (capitalize, ignore N/A, errors, etc.)
            valid_emotions = [str(log[4]).strip().capitalize() for log in logs if log[4] and isinstance(log[4], str) and str(log[4]).strip().lower() not in ["n/a", "undetected", "crop error", "processing error", ""]]
            # Handle case with no *valid* emotion entries
            if not valid_emotions:
                 self.set_status("No valid emotion data found in logs.", "orange"); self.emotion_ax.clear(); self.emotion_ax.set_title("Emotion Summary"); self.emotion_ax.pie([1], labels=['No Valid Emotions']); self.emotion_ax.axis('equal'); self.emotion_canvas.draw(); return
            # Count occurrences of each valid emotion
            emotion_counts = Counter(valid_emotions); labels = list(emotion_counts.keys()); sizes = list(emotion_counts.values()); total_emotions = sum(sizes)
            print(f"Found {total_emotions} valid emotion log entries: {emotion_counts}")
            # Update the pie chart
            self.emotion_ax.clear(); self.emotion_ax.set_title(f"Overall Emotion Distribution ({total_emotions} Entries)")
            colors = plt.cm.viridis(np.linspace(0.1, 0.9, len(labels))) # Generate colors
            wedges, texts, autotexts = self.emotion_ax.pie(sizes, labels=None, colors=colors, autopct='%1.1f%%', startangle=90, pctdistance=0.85, wedgeprops={'edgecolor': 'white'}) # Plot pie chart
            plt.setp(autotexts, size=8, weight="bold", color="white"); # Style percentage text
            self.emotion_ax.legend(wedges, labels, title="Emotions", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1)); # Add legend outside chart
            self.emotion_ax.axis('equal') # Ensure pie is circular
            self.emotion_canvas.draw(); # Redraw the canvas
            self.set_status("Emotion analysis chart updated.", "green")
        except sqlite3.Error as db_err: messagebox.showerror("Database Error", f"Failed to load logs for analysis: {db_err}", parent=self.root); self.set_status("Error loading analysis data.", "red"); print(f"DB error during emotion analysis: {db_err}")
        except Exception as e: messagebox.showerror("Analysis Error", f"Failed to update emotion chart: {e}", parent=self.root); self.set_status("Error updating analysis chart.", "red"); print(f"Error updating emotion analysis: {e}"); import traceback; traceback.print_exc()

    # --- Photo Path Helper ---
    def get_employee_photo_path(self, employee_id, find_existing=True):
        # Construct the expected path for an employee's photo or find existing one
        employee_id_str = str(employee_id) # Ensure ID is string
        if not employee_id_str: return None
        # Basic sanitization for filename (replace common problematic chars)
        safe_id_str = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in employee_id_str)
        base_path = os.path.join(EMPLOYEE_PHOTO_DIR, safe_id_str)
        # Define potential extensions
        extensions = ['.jpg', '.png', '.jpeg', '.bmp']
        if find_existing:
            # Check for existing files with known extensions
            for ext in extensions:
                 path_to_check = base_path + ext
                 if os.path.exists(path_to_check): return path_to_check
            return None # Return None if no photo found
        else:
            # Return the default path for saving (using .jpg)
            return base_path + '.jpg'

    # --- Utility Functions ---
    def set_status(self, message, color="black"):
        # Update the status bar text and color (runs on main thread)
        def _update(): # Inner function to run via 'after'
            if self.shutting_down: return # Don't update if shutting down
            try:
                 # Check if status label exists before configuring
                 if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                      self.status_label.config(text=f"Status: {message}", foreground=color)
            except tk.TclError: pass # Ignore errors if widget destroyed during shutdown
        # Schedule the update on the main thread
        if hasattr(self, 'root') and self.root.winfo_exists(): self.root.after(0, _update)

    # --- Closing Handler (UPDATED) ---
    def on_closing(self):
        # Custom handler for window close event (X button)
        print("Close button clicked...");
        if messagebox.askokcancel("Quit", "Are you sure you want to exit the Application?", parent=self.root):
            self.shutting_down = True # Set shutdown flag immediately
            self.set_status("Closing application...", "orange"); # Update status if possible
            print("Stopping camera event...")
            self.stop_video_event.set() # Signal video loop thread to stop

            # Wait for the video thread to finish
            if self.video_thread and self.video_thread.is_alive():
                print("Waiting for camera thread to join...")
                self.video_thread.join(timeout=2.0) # Wait up to 2 seconds
            if self.video_thread and self.video_thread.is_alive():
                print("Warning: Camera thread did not stop/join in time.")
            else:
                print("Camera thread joined successfully.")

            # Close Matplotlib figure if it exists
            try:
                if hasattr(self, 'emotion_fig'): plt.close(self.emotion_fig); print("Closed Matplotlib plot figure.")
            except Exception as e: print(f"Error closing plot figure: {e}")

            # --- Quit mainloop BEFORE destroying window ---
            print("Quitting Tkinter main loop...")
            try:
                # Check if root exists before calling quit
                if hasattr(self, 'root') and self.root.winfo_exists():
                     self.root.quit() # Stop the mainloop, helps cancel pending 'after' jobs
            except tk.TclError as e: print(f"Error calling root.quit() (window might already be gone): {e}")
            # --- End of quit() addition ---

            print("Destroying Tkinter window (if necessary)...");
            try:
                # Destroy the window (might be redundant after quit, but ensures cleanup)
                if hasattr(self, 'root') and self.root.winfo_exists(): self.root.destroy()
            except tk.TclError as e: print(f"Error destroying root window (might already be closed): {e}")
        else:
            # User cancelled the exit dialog
            print("Exit cancelled by user.")

# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Offline Attendance System...")
    # Ensure database is set up correctly
    print("Checking database status...")
    # Run setup regardless of existence to handle schema updates/verification
    setup_database()

    # Ensure employee photo directory exists
    print("Checking employee photo directory...")
    if not os.path.exists(EMPLOYEE_PHOTO_DIR):
        try: os.makedirs(EMPLOYEE_PHOTO_DIR); print(f"Created directory: {EMPLOYEE_PHOTO_DIR}")
        except OSError as e: print(f"FATAL ERROR: Could not create directory '{EMPLOYEE_PHOTO_DIR}': {e}"); exit()
    else:
        print(f"Employee photo directory '{EMPLOYEE_PHOTO_DIR}' exists.")

    # Initialize Tkinter root window
    print("Initializing Tkinter...")
    root = tk.Tk()
    try:
        # Create and run the main application instance
        print("Creating Application instance...")
        app = AttendanceApp(root);
        print("Starting Tkinter main loop...");
        root.mainloop(); # Start the GUI event loop - execution blocks here until window closes
        print("Application main loop finished.") # This line runs after root.quit() or window close
    except Exception as main_err:
        # Catch and report unexpected errors during app initialization or runtime
        print(f"\n--- UNHANDLED FATAL ERROR IN MAIN APPLICATION ---");
        import traceback; traceback.print_exc()
        try:
            # Try to show an error popup if Tkinter is still minimally functional
            messagebox.showerror("Fatal Application Error", f"An unexpected error occurred:\n{main_err}\n\nApplication will now exit. Check console for details.")
        except:
            print("Could not display fatal error message box.") # Fallback if GUI is completely broken
        # Attempt to destroy window cleanly on fatal error
        if 'root' in locals() and root and root.winfo_exists():
            try: root.destroy()
            except: pass
    print("Offline Attendance System finished.")