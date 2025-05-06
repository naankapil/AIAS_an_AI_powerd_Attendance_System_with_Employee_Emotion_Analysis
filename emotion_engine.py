# emotion_engine.py (Improved Error Handling for Model Loading - Updated)
from deepface import DeepFace
import cv2
import numpy as np
import logging
import time
import os

# --- Optional: Suppress excessive logging ---
# os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
# logging.getLogger('tensorflow').setLevel(logging.ERROR)
# logging.getLogger('deepface').setLevel(logging.WARN)

# Note: Emotion model is loaded automatically by DeepFace.analyze when first needed.
# No explicit build_model("Emotion") call is required here.
# We'll rely on the error handling within detect_emotion_from_face.
EMOTION_MODEL_LOADED = True # Assume it can load, handle errors in analyze
EMOTION_MODEL_ERROR_MESSAGE = ""


def detect_emotion_from_face(face_image_np):
    """Detects dominant emotion from a face image (NumPy array)."""
    # Note: The EMOTION_MODEL_LOADED check here is less critical now,
    # as loading happens within analyze, but kept for consistency.
    if not EMOTION_MODEL_LOADED:
        print("Emotion Engine: Global flag indicates model loading failed previously.")
        return None # Model loading likely failed permanently if this flag was set False elsewhere

    if face_image_np is None or face_image_np.size == 0:
        # print("Emotion Engine: Input image is empty.") # Optional: uncomment for debugging
        return None
    if not isinstance(face_image_np, np.ndarray):
        print("Emotion Engine: Input is not a numpy array.")
        return None
    # Ensure input is uint8, as expected by DeepFace
    if face_image_np.dtype != np.uint8:
        try:
            face_image_np = face_image_np.astype(np.uint8)
            # print("Emotion Engine: Converted input image to uint8.") # Optional debug message
        except Exception as e:
            print(f"Emotion Engine: Failed to convert image to uint8 - {e}")
            return None
    # Ensure 3 dimensions (height, width, channel) even for grayscale, DeepFace might handle it but doesn't hurt
    if face_image_np.ndim == 2:
        try:
            face_image_np = cv2.cvtColor(face_image_np, cv2.COLOR_GRAY2BGR)
            # print("Emotion Engine: Converted grayscale image to BGR.") # Optional debug message
        except Exception as e:
             print(f"Emotion Engine: Failed to convert grayscale image to BGR - {e}")
             return None

    if face_image_np.shape[0] < 20 or face_image_np.shape[1] < 20: # Avoid processing tiny face crops
         # print("Emotion Engine: Face crop too small.") # Optional debug message
         return None

    try:
        # DeepFace.analyze handles model loading internally if not already loaded
        result = DeepFace.analyze(
            img_path=face_image_np,
            actions=['emotion'],
            enforce_detection=False, # Assume input is already a face crop
            detector_backend='skip', # Skip detection if enforce_detection is False
            silent=True # Suppress DeepFace's internal console output
        )
        # DeepFace returns a list of dicts, even for single image if enforce_detection=False
        if isinstance(result, list) and len(result) > 0:
            # Access the first dictionary in the list
            dominant_emotion = result[0].get('dominant_emotion', None)
            return dominant_emotion
        elif isinstance(result, dict): # Fallback if it returns dict directly (older versions?)
             dominant_emotion = result.get('dominant_emotion', None)
             return dominant_emotion
        else:
             # print(f"Emotion Engine: Unexpected result type from DeepFace.analyze: {type(result)}") # Optional debug
             return None
    except ValueError as ve:
        # Specific errors like "Face could not be detected" might occur if enforce_detection=True,
        # but with enforce_detection=False, other ValueErrors might pop up.
        # Also catches "No face detected" errors if somehow detection runs.
        # print(f"Emotion Engine: ValueError during analysis - {ve}") # Optional debug
        return None # Return None if no face detected or other value error
    except Exception as e:
        # Catch any other unexpected errors during analysis
        print(f"Emotion Engine: Unexpected error during DeepFace analysis: {e}")
        # Consider setting EMOTION_MODEL_LOADED = False here if the error seems permanent
        # global EMOTION_MODEL_LOADED, EMOTION_MODEL_ERROR_MESSAGE
        # EMOTION_MODEL_LOADED = False
        # EMOTION_MODEL_ERROR_MESSAGE = str(e)
        return None

# --- Example Usage (Keep commented out) ---
# if __name__ == '__main__':
#    # Test code if needed
#    # img = cv2.imread("path_to_face_image.jpg")
#    # if img is not None:
#    #    emotion = detect_emotion_from_face(img)
#    #    print(f"Detected emotion: {emotion}")
#    # else:
#    #    print("Could not load test image.")
#    pass