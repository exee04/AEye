import threading
from SystemModules.ButtonModule.SmartButton import SmartButton
import time
from queue import Queue
from gpiozero import Button, DigitalOutputDevice
from google.cloud import speech
import sounddevice as sd
import numpy as np
from scipy.signal import resample_poly
from scipy.io.wavfile import write
from SystemModules.Prompts.SystemPrompts import QUIZ_PROMPT_MAP
from SystemModules.Prompts.SystemPrompts import EDUCATION_PROMPT_MAP
from SystemModules.Prompts.SystemPrompts import MAIN_PROMPT_MAP
from SystemModules.Prompts.SystemPrompts import COMMON_PROMPT_MAP
import difflib
import os
import subprocess
import random
import mediapipe as mp
from datetime import datetime
import cv2
from ultralytics import YOLO
from picamera2 import Picamera2
import re
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import json
from supabase import create_client, Client
from dotenv import load_dotenv
import socket
# Add Vosk imports
try:
	from vosk import Model as VoskModel, KaldiRecognizer
except ImportError:
	VoskModel = None
	KaldiRecognizer = None
from pyzbar import pyzbar

# Load environment variables
load_dotenv('db.env')  # Specify db.env as the environment file

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
	def __init__(self):
		self.supabase: Client = None
		self.initialize_client()

	def initialize_client(self):
		"""Initialize Supabase client"""
		try:
			url = os.getenv('SUPABASE_URL')
			key = os.getenv('SUPABASE_KEY')
			if not url or not key:
				raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")
			
			self.supabase = create_client(url, key)
			logger.info("Successfully initialized Supabase client")
		except Exception as e:
			logger.error(f"Error initializing Supabase client: {e}")
			raise

	def save_quiz_result(self, user_id, letter, is_correct, response_time):
		"""Update user_stats for quiz result (no quiz_results table)"""
		try:
			# Fetch current stats for this user and letter
			stats_resp = self.supabase.table('user_stats') \
				.select('*') \
				.eq('user_id', user_id) \
				.eq('alphanumeric_char', letter) \
				.execute()
			stats = stats_resp.data[0] if stats_resp.data else None

			# Calculate new values
			attempts = (stats['attempts'] if stats else 0) + 1
			correct_count = (stats['correct_count'] if stats else 0) + (1 if is_correct else 0)
			total_response_time = (stats['avg_response_time'] * stats['attempts'] if stats and stats['attempts'] else 0) + response_time
			avg_response_time = total_response_time / attempts

			# Upsert user_stats for this user and letter
			self.supabase.table('user_stats').upsert({
				'user_id': user_id,
				'alphanumeric_char': letter,
				'correct_count': correct_count,
				'attempts': attempts,
				'avg_response_time': avg_response_time
			}).execute()

			logger.info(f"Successfully saved quiz result for user {user_id}, letter {letter}")
		except Exception as e:
			logger.error(f"Error saving quiz result: {e}")
			raise

	def get_user_stats(self, user_id, letter=None):
		"""Get user statistics from database. If letter is provided, filter by letter."""
		try:
			query = self.supabase.table('user_stats').select('*').eq('user_id', user_id)
			if letter:
				query = query.eq('alphanumeric_char', letter)
			stats_resp = query.execute()
			if not stats_resp.data:
				return None
			return stats_resp.data
		except Exception as e:
			logger.error(f"Error getting user stats: {e}")
			raise

# Initialize database manager
db_manager = DatabaseManager()

def test_supabase_connection():
	"""Test the Supabase connection by reading user_stats."""
	try:
		# Try to fetch a single row from user_stats
		result = db_manager.supabase.table('user_stats').select('*').limit(1).execute()
		logger.info("Successfully connected to Supabase!")
		return True
	except Exception as e:
		logger.error(f"Failed to connect to Supabase: {e}")
		return False

# Test connection on startup
if test_supabase_connection():
	logger.info("Database connection test passed")
else:
	logger.error("Database connection test failed")

def is_connected():
	"""Check if the device is connected to the internet."""
	try:
		# Try to connect to a public DNS server
		socket.create_connection(("8.8.8.8", 53), timeout=2)
		return True
	except OSError:
		return False

# Check connectivity at startup
online_mode = is_connected()
if online_mode:
	logger.info("Internet connection detected. Online mode enabled.")
else:
	logger.info("No internet connection. Offline mode enabled.")

@dataclass
class SystemState:
	main_mode: bool = True
	active_educ_mode: bool = False
	active_learn_mode: bool = False
	active_quiz_mode: bool = False
	active_question: bool = False
	on_default_language: bool = True
	on_volume_control: bool = False
	current_volume: int = 100
	voice_speed: int = 150
	current_language: str = "en-US"
	last_prompt: str = ""
	last_transcript: str = ""
	prompt_map: Dict = field(default_factory=lambda: MAIN_PROMPT_MAP)
	marker_corners: Optional[np.ndarray] = None
	braille_positions: List[Dict] = field(default_factory=list)
	braille_scanned: bool = False
	base_marker_center: Optional[Tuple[int, int]] = None
	last_scan_time: float = 0.0
	online_mode: bool = True
	speech_recognizer: str = "google"
	current_user_id: Optional[str] = None  # None if not logged in
	current_user_email: Optional[str] = None
	current_user_full_name: Optional[str] = None

	def __post_init__(self):
		if self.braille_positions is None:
			self.braille_positions = []

class StateManager:
	def __init__(self):
		self.state = SystemState()

	def toggle_mode(self):
		self.state.main_mode = not self.state.main_mode
		logger.info(f"Current mode: {'main mode' if self.state.main_mode else 'secondary mode'}")

	def toggle_learning_mode(self):
		self.state.active_learn_mode = not self.state.active_learn_mode
		self.state.prompt_map = EDUCATION_PROMPT_MAP
		logger.info(f"Learn Mode = {self.state.active_learn_mode}")

	def toggle_quiz_mode(self):
		# Guard: Prevent enabling quiz mode in offline mode or if not logged in
		if not self.state.online_mode:
			TTS("Quiz mode is not available while offline.")
			logger.info("Attempted to enable quiz mode while offline. Action blocked.")
			self.state.active_quiz_mode = False
			return
		if not self.state.current_user_id:
			TTS("Please scan your QR code to log in before using quiz mode.")
			logger.info("Attempted to enable quiz mode without user logged in. Action blocked.")
			self.state.active_quiz_mode = False
			return
		self.state.active_quiz_mode = not self.state.active_quiz_mode
		self.state.prompt_map = QUIZ_PROMPT_MAP
		logger.info(f"Quiz Mode = {self.state.active_quiz_mode}")

	def change_language(self):
		self.state.on_default_language = not self.state.on_default_language
		self.state.current_language = "en-US" if self.state.on_default_language else "fil-PH"
		logger.info(f"Language changed to {self.state.current_language}")

	def update_volume(self, delta: int):
		new_volume = self.state.current_volume + delta
		if 0 <= new_volume <= 200:
			self.state.current_volume = new_volume
			logger.info(f"Volume set to {self.state.current_volume}")
			return True
		return False

	def update_voice_speed(self, delta: int):
		new_speed = self.state.voice_speed + delta
		if 100 <= new_speed <= 280:
			self.state.voice_speed = new_speed
			logger.info(f"Voice speed set to {self.state.voice_speed}")
			return True
		return False

class CameraManager:
	def __init__(self):
		self.picam2 = None
		self.is_running = False

	def cleanup(self):
		"""Properly cleanup camera resources"""
		if self.picam2 and self.is_running:
			try:
				self.picam2.stop()
				self.picam2.close()
				self.is_running = False
				logger.info("Camera resources cleaned up successfully")
			except Exception as e:
				logger.error(f"Error during camera cleanup: {e}")
		self.picam2 = None

	@contextmanager
	def initialize_camera(self):
		"""Initialize camera with proper error handling"""
		try:
			# Cleanup any existing camera instance
			self.cleanup()
			
			# Initialize new camera instance
			self.picam2 = Picamera2()
			config = self.picam2.create_still_configuration(main={"format": "RGB888", "size": (640, 480)})
			self.picam2.configure(config)
			self.picam2.start()
			time.sleep(1)  # Camera warm-up
			self.is_running = True
			logger.info("Camera initialized successfully")
			yield self.picam2
		except Exception as e:
			logger.error(f"Failed to initialize camera: {e}")
			self.cleanup()  # Ensure cleanup on error
			raise
		finally:
			self.cleanup()  # Ensure cleanup when context exits

class ModelManager:
	def __init__(self):
		self.yolo_model = None
		self.hands = None
		self._initialized = False
		self._initialization_lock = threading.Lock()

	def initialize_models(self):
		"""Initialize models only when needed"""
		with self._initialization_lock:
			if self._initialized:
				return True

			try:
				logger.info("Starting model initialization...")
				
				# Initialize YOLO model
				logger.info("Initializing YOLO model...")
				model_path = "/home/ky/AEye/AI_Models/best_ncnn_model"
				if not os.path.exists(model_path):
					raise FileNotFoundError(f"YOLO model not found at {model_path}")
				self.yolo_model = YOLO(model_path, task='detect')  # Explicitly set task
				logger.info("YOLO model initialized successfully")

				# Initialize MediaPipe hands
				logger.info("Initializing MediaPipe hands...")
				mp_hands = mp.solutions.hands
				self.hands = mp_hands.Hands(
					static_image_mode=False,
					max_num_hands=1,
					min_detection_confidence=0.3,
					min_tracking_confidence=0.3
				)
				logger.info("MediaPipe hands initialized successfully")

				self._initialized = True
				return True
			except Exception as e:
				logger.error(f"Failed to initialize models: {e}")
				self.cleanup()  # Clean up any partially initialized models
				return False

	def cleanup(self):
		"""Clean up model resources"""
		if self.hands:
			try:
				self.hands.close()
			except Exception as e:
				logger.error(f"Error closing MediaPipe hands: {e}")
		
		self.yolo_model = None
		self.hands = None
		self._initialized = False

	def ensure_initialized(self):
		"""Ensure models are initialized before use"""
		if not self._initialized:
			return self.initialize_models()
		return True

# Initialize managers
state_manager = StateManager()
camera_manager = CameraManager()
model_manager = ModelManager()

# Initialize vibration module
vibration_module = DigitalOutputDevice(16)

def vibrate():
	"""Activate vibration module for 1 second"""
	vibration_module.on()
	time.sleep(1)
	vibration_module.off()

def toggleMode():
	state_manager.toggle_mode()

def EducMode():
	print("Education Mode")
	mainBtn.when_held = lambda: threading.Thread(target=speak).start()
	state_manager.state.active_educ_mode = True
	state_manager.state.prompt_map = MAIN_PROMPT_MAP
	funcButton2.on_tap = ScoreCheckMode
	
	TTS("Education Mode")

	# Initialize models in a separate thread
	def init_models():
		if not model_manager.initialize_models():
			TTS("Failed to initialize AI models. Please restart the system.")
			return False
		return True

	# Start model initialization in background
	init_thread = threading.Thread(target=init_models)
	init_thread.start()

	# Load braille positions from JSON
	try:
		with open('braille_scan_20250520_231629.json', 'r') as f:
			braille_data = json.load(f)
			state_manager.state.braille_positions = braille_data['braille_positions']
			print("✅ Loaded braille positions from JSON")
	except Exception as e:
		logger.error(f"Failed to load braille positions: {e}")
		TTS("Failed to load braille positions. Please check the JSON file.")
		return

	# Wait for model initialization to complete
	init_thread.join()
	if not model_manager._initialized:
		return

	try:
		with camera_manager.initialize_camera() as picam2:
			center_history = []
			current_marker_center = None

			# ArUco marker parameters for distance calculation
			marker_size = 0.05  # Size of the ArUco marker in meters (5cm)
			
			# Get camera parameters from picam2
			camera_info = picam2.camera_properties
			width = camera_info['PixelArraySize'][0]
			height = camera_info['PixelArraySize'][1]
			
			# Create camera matrix with proper focal length
			focal_length = max(width, height)
			camera_matrix = np.array([
				[focal_length, 0, width/2],
				[0, focal_length, height/2],
				[0, 0, 1]
			], dtype=np.float32)
			
			dist_coeffs = np.zeros(5, dtype=np.float32)

			# Define the coordinate axes points
			axis_length = 0.1  # Length of the axes in meters
			axis_points = np.float32([[0, 0, 0],
									[axis_length, 0, 0],
									[0, axis_length, 0],
									[0, 0, axis_length]])

			while state_manager.state.main_mode and state_manager.state.active_educ_mode:
				try:
					# Process voice commands
					if ((state_manager.state.last_transcript != state_manager.state.last_prompt) 
						and not state_manager.state.active_quiz_mode):
						state_manager.state.last_transcript = state_manager.state.last_prompt
						print(f"Processing transcript: {state_manager.state.last_prompt}")
						CheckForKeywords(state_manager.state.last_prompt)

					# Capture and validate frame
					frame = picam2.capture_array()
					if frame is None:
						logger.warning("Failed to capture frame")
						continue

					# Process frame for ArUco marker
					gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
					aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
					parameters = cv2.aruco.DetectorParameters()
					aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
					corners, ids, _ = aruco_detector.detectMarkers(gray)

					current_time = time.time()
					marker_detected = False

					# Reset current_marker_center if no marker is detected
					if ids is None or 1 not in ids:
						current_marker_center = None
					else:
						# Process detected marker
						idx = list(ids).index(1)
						state_manager.state.marker_corners = corners[idx][0]
						current_marker_center = (
							int((state_manager.state.marker_corners[0][0] + state_manager.state.marker_corners[2][0]) / 2),
							int((state_manager.state.marker_corners[0][1] + state_manager.state.marker_corners[2][1]) / 2)
						)
						marker_detected = True
						cv2.circle(frame, current_marker_center, 5, (255, 0, 0), -1)
						
						# Calculate distance and orientation
						marker_points = np.array([
							[-marker_size/2, marker_size/2, 0],
							[marker_size/2, marker_size/2, 0],
							[marker_size/2, -marker_size/2, 0],
							[-marker_size/2, -marker_size/2, 0]
						], dtype=np.float32)
						
						ret, rvec, tvec = cv2.solvePnP(
							marker_points,
							corners[idx][0],
							camera_matrix,
							dist_coeffs
						)
						distance = np.linalg.norm(tvec)
						
						# Get rotation matrix from rotation vector
						rot_matrix, _ = cv2.Rodrigues(rvec)
						
						# Project the coordinate axes onto the image
						imgpts, jac = cv2.projectPoints(axis_points, rvec, tvec, camera_matrix, dist_coeffs)
						origin = tuple(map(int, imgpts[0].ravel()))
						x_axis = tuple(map(int, imgpts[1].ravel()))
						y_axis = tuple(map(int, imgpts[2].ravel()))
						z_axis = tuple(map(int, imgpts[3].ravel()))

						# Draw the coordinate axes
						cv2.line(frame, origin, x_axis, (0, 0, 255), 3)  # X-axis in red
						cv2.line(frame, origin, y_axis, (0, 255, 0), 3)  # Y-axis in green
						cv2.line(frame, origin, z_axis, (255, 0, 0), 3)  # Z-axis in blue

						# Add labels for the axes
						cv2.putText(frame, 'X', x_axis, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
						cv2.putText(frame, 'Y', y_axis, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
						cv2.putText(frame, 'Z', z_axis, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
						
						# Display distance and orientation
						cv2.putText(frame, f"Distance: {distance*100:.1f} cm",
								  (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
						
						# Display Euler angles
						angles = np.degrees(rvec)
						cv2.putText(frame, f"Rotation (deg): X:{angles[0][0]:.1f} Y:{angles[1][0]:.1f} Z:{angles[2][0]:.1f}",
								  (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
						
						# Update center history
						center_history.append(current_marker_center)
						if len(center_history) > 15:
							center_history.pop(0)

						# Draw braille positions based on marker center and orientation
						if current_marker_center:
							for braille in state_manager.state.braille_positions:
								rel_x, rel_y = braille["relative"]
								label = braille["label"]
								box_w, box_h = braille["size"]

								# Convert relative position to 3D point (in marker's coordinate system)
								point_3d = np.array([
									rel_x/1000.0,  # Convert mm to meters
									-rel_y/1000.0,  # Invert Y and convert to meters
									0
								], dtype=np.float32)
								
								# Transform point using rotation matrix
								point_3d_rotated = np.dot(rot_matrix, point_3d)
								
								# Project the transformed point back to 2D
								point_2d, _ = cv2.projectPoints(
									point_3d_rotated.reshape(1, 1, 3),
									np.zeros(3, dtype=np.float32),
									tvec,
									camera_matrix,
									dist_coeffs
								)
								
								# Get the projected point
								abs_x = int(point_2d[0][0][0])
								abs_y = int(point_2d[0][0][1])

								# Scale the box size based on distance and perspective
								scale_factor = 1.0 / (distance + 0.1)
								base_size = 60
								scaled_w = int(base_size * scale_factor)
								scaled_h = int(base_size * scale_factor)

								# Ensure minimum size for visibility
								scaled_w = max(scaled_w, 30)
								scaled_h = max(scaled_h, 30)

								top_left = (int(abs_x - scaled_w/2), int(abs_y - scaled_h/2))
								bottom_right = (int(abs_x + scaled_w/2), int(abs_y + scaled_h/2))

								# Draw rectangle with adjusted size
								cv2.rectangle(frame, top_left, bottom_right, (0, 255, 0), 2)
								
								# Adjust text size based on box size
								text_scale = max(0.3, min(0.7, scale_factor))
								cv2.putText(frame, label, 
										  (top_left[0], top_left[1] - 5), 
										  cv2.FONT_HERSHEY_SIMPLEX, 
										  text_scale, 
										  (0, 255, 0), 
										  2)

							# Process hand detection
							process_hand_detection(frame, current_marker_center, state_manager.state.braille_positions)

					# Display mode status
					mode_text = "Learning Mode" if state_manager.state.active_learn_mode else "Quiz Mode" if state_manager.state.active_quiz_mode else "Main Mode"
					cv2.putText(frame, mode_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

					# Show frame
					cv2.imshow("frame", frame)
					if cv2.waitKey(1) & 0xFF == ord('q'):
						break

				except Exception as e:
					logger.error(f"Error in main loop: {e}")
					continue

	except Exception as e:
		logger.error(f"Camera error: {e}")
		TTS("Camera error occurred. Please restart the system.")
	finally:
		model_manager.cleanup()
		cv2.destroyAllWindows()

def process_hand_detection(frame, current_marker_center, braille_positions):
	try:
		frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
		result = model_manager.hands.process(frame_bgr)

		if result.multi_hand_landmarks:
			for handLms in result.multi_hand_landmarks:
				h, w, _ = frame.shape
				
				# Draw all hand landmarks for debugging
				for id, lm in enumerate(handLms.landmark):
					cx, cy = int(lm.x * w), int(lm.y * h)
					# Draw different colors for different landmarks
					if id == 8:  # Index finger tip
						cv2.circle(frame, (cx, cy), 8, (0, 0, 255), -1)  # Red for index finger tip
					elif id in [5, 6, 7]:  # Index finger joints
						cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)  # Green for index finger joints
					else:
						cv2.circle(frame, (cx, cy), 3, (255, 0, 0), -1)  # Blue for other landmarks

				# Get index finger tip position
				fingertip = handLms.landmark[8]
				fx, fy = int(fingertip.x * w), int(fingertip.y * h)

				# Draw detection radius around fingertip
				cv2.circle(frame, (fx, fy), 20, (0, 255, 255), 2)  # Yellow circle for detection radius

				for braille in braille_positions:
					rel_x, rel_y = braille["relative"]
					abs_x = current_marker_center[0] + rel_x
					abs_y = current_marker_center[1] + rel_y

					# Draw detection area for each braille position
					cv2.circle(frame, (abs_x, abs_y), 20, (255, 255, 0), 2)  # Cyan circle for braille detection area

					# Check if fingertip is within the braille position
					if (abs(fx - abs_x) < 20 and abs(fy - abs_y) < 20):
						# Draw green circle when detected
						cv2.circle(frame, (abs_x, abs_y), 20, (0, 255, 0), 2)
						
						currentBrailleLetter = braille['label']
						
						# Add timestamp tracking for each braille position
						current_time = time.time()
						if not hasattr(braille, 'touch_start_time'):
							braille['touch_start_time'] = current_time
							braille['touch_duration'] = 0
						else:
							braille['touch_duration'] = current_time - braille['touch_start_time']
						
						# Display touch duration
						if braille['touch_duration'] > 0:
							cv2.putText(frame, f"Touch: {braille['touch_duration']:.1f}s", 
									  (abs_x - 40, abs_y - 30), 
									  cv2.FONT_HERSHEY_SIMPLEX, 
									  0.5, 
									  (0, 255, 0), 
									  2)
						
						# Only trigger if finger has been on the position for at least 1 second
						if braille['touch_duration'] >= 1.0:
							if state_manager.state.active_learn_mode:
								TTS(f"You are touching letter {currentBrailleLetter}")
								vibrate()  # Add vibration feedback
								time.sleep(1)  # Reduced sleep time to match new duration
								# Reset touch tracking
								braille['touch_start_time'] = None
								braille['touch_duration'] = 0
								break
							elif state_manager.state.active_quiz_mode:
								run_quiz_question(currentBrailleLetter)
								vibrate()  # Add vibration feedback
								# Reset touch tracking
								braille['touch_start_time'] = None
								braille['touch_duration'] = 0
								break
					else:
						# Reset touch tracking if finger moves away
						if hasattr(braille, 'touch_start_time'):
							braille['touch_start_time'] = None
							braille['touch_duration'] = 0

				# Draw coordinates for debugging
				cv2.putText(frame, f"Finger: ({fx}, {fy})", 
						  (10, frame.shape[0] - 20), 
						  cv2.FONT_HERSHEY_SIMPLEX, 
						  0.5, 
						  (255, 255, 255), 
						  2)

	except Exception as e:
		logger.error(f"Error in hand detection: {e}")

def run_quiz_question(currentBrailleLetter):
	"""Run a single quiz question"""
	correct_letter = currentBrailleLetter.upper()
	print("What letter is this?")
	TTS("What letter is this?")

	# Reset the transcript tracking
	state_manager.state.last_transcript = ""
	state_manager.state.last_prompt = ""

	# Wait for user response
	start_time = time.time()
	timeout = 10  # 10 second timeout for answer
	
	while time.time() - start_time < timeout:
		if state_manager.state.last_transcript != state_manager.state.last_prompt:
			user_input = state_manager.state.last_transcript
			state_manager.state.last_prompt = state_manager.state.last_transcript

			extracted = extract_letter_answer(user_input)
			if extracted:
				print(f"User answered: {extracted}")
				is_correct = extracted == correct_letter
				response_time = time.time() - start_time
				
				# Save quiz result to database
				try:
					db_manager.save_quiz_result(
						user_id="default_user",  # Replace with actual user ID
						letter=correct_letter,
						is_correct=is_correct,
						response_time=response_time
					)
				except Exception as e:
					logger.error(f"Error saving quiz result: {e}")

				if is_correct:
					print("Correct!")
					TTS("Correct!")
					vibrate()  # Add vibration feedback for correct answer
				else:
					print(f"Wrong. The correct answer was {correct_letter}")
					TTS(f"Wrong. The correct answer was {correct_letter}")
				return
			else:
				print("Sorry, I didn't catch that. Please say the letter again.")
				TTS("Sorry, I didn't catch that. Please say the letter again.")
				# Reset the transcript tracking to avoid repeated prompts
				state_manager.state.last_transcript = ""
				state_manager.state.last_prompt = ""
		
		time.sleep(0.1)  # Small delay to prevent CPU overuse
	
	# Timeout reached
	print("Time's up!")
	TTS("Time's up!")

def ScoreCheckMode():
	state_manager.state.active_educ_mode = False

def toggleLearningMode():
	state_manager.toggle_learning_mode()

def toggleQuizMode():
	state_manager.toggle_quiz_mode()

def toggleQuestionMode():
	state_manager.state.active_question = not state_manager.state.active_question

def wait_button():
	queue = Queue() 
	funcButton1.button.when_pressed = queue.put
	funcButton2.button.when_pressed = queue.put
	funcButton4.button.when_pressed = queue.put
	e = queue.get()
	return e.pin.number

def wait_volbutton():
	queue = Queue()
	volUpBtn.when_pressed = queue.put
	volDownBtn.when_pressed = queue.put
	e = queue.get()
	return e.pin.number

def TTS(text):
	threading.Thread(target=lambda: subprocess.run([
		'espeak-ng', 
		"-a", str(state_manager.state.current_volume),
		"-s", str(state_manager.state.voice_speed),
		"-p", "70",
		text
	])).start()

# Vosk model path (set your actual path here)
VOSK_MODEL_PATH = "/home/ky/AEye/AEyeProj/VoskModels/vosk-model-en-us-0.22"
VOSK_SAMPLE_RATE = 16000
vosk_model = None
vosk_recognizer = None

if not online_mode and VoskModel is not None:
	try:
		vosk_model = VoskModel(VOSK_MODEL_PATH)
		vosk_recognizer = KaldiRecognizer(vosk_model, VOSK_SAMPLE_RATE)
		logger.info("Vosk model loaded for offline speech recognition.")
	except Exception as e:
		logger.error(f"Failed to load Vosk model: {e}")

def speak():
	transcript = ""
	audio_data = []

	# Record audio while button is held
	while mainBtn.is_held:
		print("Holding")
		frame = sd.rec(int(0.5 * fs), samplerate=fs, channels=1, dtype='int16')
		sd.wait()
		audio_data.append(frame)

	if not audio_data:
		return

	# Concatenate recorded chunks 
	audio_data = np.concatenate(audio_data, axis=0)

	# Resample using fast method
	audio_resampled = resample_poly(audio_data.flatten(), target_fs, fs)
	audio_resampled = audio_resampled.astype('int16')

	# Save WAV file
	write(filename, target_fs, audio_resampled)
	print(f"Saved to {filename}")

	if state_manager.state.speech_recognizer == 'google':
		# Google Speech-to-Text
		with open(filename, "rb") as audio_file:
			content = audio_file.read()

		audio = speech.RecognitionAudio(content=content)

		try:
			response = client.recognize(config=config, audio=audio)
			for result in response.results:
				transcript = result.alternatives[0].transcript
				print("Transcript:", transcript)
				state_manager.state.last_prompt = transcript
				CheckForKeywords(transcript)

		except Exception as e:
			print("Google transcription error:", e)

	elif state_manager.state.speech_recognizer == 'vosk' and vosk_recognizer is not None:
		import wave
		try:
			wf = wave.open(filename, "rb")
			vosk_recognizer.Reset()
			while True:
				data = wf.readframes(4000)
				if len(data) == 0:
					break
				if vosk_recognizer.AcceptWaveform(data):
					res = json.loads(vosk_recognizer.Result())
					transcript = res.get("text", "")
					print("Transcript:", transcript)
					state_manager.state.last_prompt = transcript
					CheckForKeywords(transcript)
					break
			wf.close()
		except Exception as e:
			print("Vosk transcription error:", e)

	# Clean up
	if os.path.exists(filename):
		os.remove(filename)

def changeLanguage():
	state_manager.change_language()

def changeTalkingSpeed():
	state_manager.state.on_volume_control = not state_manager.state.on_volume_control

def volumeControl():
	print("Volume control active")
	while True:
		b = wait_volbutton()
		if state_manager.state.on_volume_control:
			if b == 6:  # Volume up
				if state_manager.update_volume(20):
					TTS("Volume Up")
					vibrate()  # Add vibration feedback
				else:
					TTS("Max Volume")
					vibrate()  # Add vibration feedback
			elif b == 5:  # Volume down
				if state_manager.update_volume(-20):
					TTS("Volume Down")
					vibrate()  # Add vibration feedback
				else:
					TTS("No Volume")
					vibrate()  # Add vibration feedback
		else:
			if b == 6:  # Speed up
				if state_manager.update_voice_speed(10):
					TTS("Increasing Talking Speed")
					vibrate()  # Add vibration feedback
				else:
					TTS("Max Talking Speed")
					vibrate()  # Add vibration feedback
			elif b == 5:  # Speed down
				if state_manager.update_voice_speed(-10):
					TTS("Decreasing Talking Speed")
					vibrate()  # Add vibration feedback
				else:
					TTS("Minimum Talking Speed")
					vibrate()  # Add vibration feedback
		time.sleep(0.2)

def get_best_match(prompt: str, threshold=0.65):
	prompt = prompt.lower()
	PROMPT_MAP_AND_COMMON_MAP = {**state_manager.state.prompt_map, **COMMON_PROMPT_MAP}
	best_match = difflib.get_close_matches(prompt, PROMPT_MAP_AND_COMMON_MAP.keys(), n=1, cutoff=threshold)
	if best_match:
		logger.info(f"Matched prompt: {best_match[0]}")
		return PROMPT_MAP_AND_COMMON_MAP[best_match[0]]
	logger.warning(f"No match found for prompt: {prompt}")
	return None

def handle_command(flag):
	if not flag:
		return
		
	logger.info(f"Handling command: {flag}")
	match flag:
		case "LEARN_MODE":
			state_manager.toggle_learning_mode()
			TTS("Entering learning mode. Touch the braille letters to learn them.")
		case "QUIZ_MODE":
			state_manager.toggle_quiz_mode()
			TTS("Entering quiz mode. I'll ask you to identify letters.")
		case "OBJECT_DETECTION":
			TTS("Object detection mode is not available in this version.")
		case "DISTANCE_CHECK":
			TTS("Distance check mode is not available in this version.")
		case "DESCRIBE_LETTER":
			if state_manager.state.active_learn_mode:
				TTS("Touch a letter to learn about it.")
			else:
				TTS("Please enter learning mode first.")
		case "REPEAT_DESCRIPTION":
			TTS("Touch a letter to hear its description again.")
		case "ANSWER":
			if state_manager.state.active_quiz_mode:
				TTS("Please touch the letter you think is correct.")
			else:
				TTS("Please enter quiz mode first.")
		case "DENY":
			TTS("Let's try another letter.")
		case "GREET":
			Greetings()
		case "STATE_MODE":
			mode = "learning" if state_manager.state.active_learn_mode else "quiz" if state_manager.state.active_quiz_mode else "main"
			TTS(f"You are in {mode} mode.")
		case "TIME_QUERY":
			TimeQuery()
		case "DATE_QUERY":
			DateQuery()
		case "CANCEL":
			state_manager.state.active_learn_mode = False
			state_manager.state.active_quiz_mode = False
			state_manager.state.prompt_map = MAIN_PROMPT_MAP
			TTS("Returning to main mode.")
		case _:
			TTS("I don't understand that command.")

def CheckForKeywords(text):
	if not text:
		return
		
	print(f"Checking keywords for: {text}")
	command_flag = get_best_match(text)
	if command_flag:
		print(f"Found command: {command_flag}")
		handle_command(command_flag)
	else:
		print("No matching command found")
		TTS("Sorry, I didn't understand that. Try saying 'help me' or 'teach me braille'.")

def Greetings():
	randomGreeting = random.randrange(0, 4)
	match randomGreeting:
		case 0:
			print("greetings 0")
			TTS("Hey")
		case 1:
			print("greetings 1")
			TTS("Hi")
		case 2:
			print("greetings 2")
			TTS("Hello")
		case 3:
			print("greetings 3")
			TTS("What's up")

def TimeQuery():
	global current_time
	randomTimeQuery = random.randrange(0, 3)
	match randomTimeQuery:
		case 0:
			print("time query 0")
			TTS("It is currently " + str(current_time))
		case 1:
			print("time query 1")
			TTS("The time is " + str(current_time))
		case 2:
			print("time query 2")
			TTS(str(current_time))
	
def DateQuery():
	global today
	randomDateQuery = random.randrange(0, 2)
	match randomDateQuery:
		case 0:
			print("date query 0")
			TTS("The current date is " + str(today))
		case 1:
			print("date query 1")
			TTS("Today is " + str(today))
		case 2:
			print("date query 2")
			TTS(str(today))

def is_stable(center_history, max_variance=20):
	if len(center_history) < 5:
		return False

	# Compute average position
	avg_x = sum([pt[0] for pt in center_history]) / len(center_history)
	avg_y = sum([pt[1] for pt in center_history]) / len(center_history)

	# Compute average distance from center
	variance = sum([
		((pt[0] - avg_x) ** 2 + (pt[1] - avg_y) ** 2) ** 0.5
		for pt in center_history
	]) / len(center_history)

	return variance < max_variance

def extract_letter_answer(transcript):
	"""
	Extract a single alphabet letter from user input.
	"""
	transcript = transcript.lower().strip()

	# Regex to match phrases like:
	# "the answer is the letter a", "letter b", "b"
	match = re.search(r'(?:the answer is|the letter|letter)?\s*([a-z])\b', transcript)

	if match:
		return match.group(1).upper()  # return as uppercase for consistency
	return None

mainMode = True

#Global variable for checking user prompts
lastPrompt = ""

# Initialize models
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
	static_image_mode=True,
	max_num_hands=1,
	min_detection_confidence=0.3,
	min_tracking_confidence=0.3)
root = os.getcwd()
yolo_model_path = os.path.join(root, 'AI_Models/best_ncnn_model')
yolo_model = YOLO(yolo_model_path)  # replace with your model path

# Load ArUco Dictionary and Detector
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
parameters = cv2.aruco.DetectorParameters()
marker_corners = None
braille_positions = []

#Button Initializations
funcButton1 = SmartButton(17) #button 1
funcButton2 = SmartButton(27) #button 2
funcButton3 = SmartButton(22) #button 3
funcButton4 = SmartButton(23) #button 4
mainBtn = Button(24, hold_time=0.1)
#mainBtn = SmartButton(24) #main button
volUpBtn = Button(6)
volDownBtn = Button(5)

onVolumeControl = True

voiceSpeed = 170
currentVolume = 200
volume = currentVolume

onDefaultLanguage = True
currentLanguage = "en-US"
language1 = "en-US"
language2 = "fil-PH"

activeEducMode = False
activeQuizMode = False
activeLearnMode = False
activeQuestion = False
activeDetectMode = False

PROMPT_MAP = None

now = datetime.now()
current_time = datetime.now().strftime("%I:%M %p")
today = datetime.now().date()
print("Current Time:", current_time)
print("Current Date:", today)

client = speech.SpeechClient() #Google API Client

#Microphone Initialization
fs = 44100  
target_fs = 16000  
filename = "output.wav"
config = speech.RecognitionConfig(
		encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
		sample_rate_hertz=target_fs,
		language_code="en-US",
	)

# Global camera usage flag
camera_in_use = False

def initialize_mode():
	state_manager.state.online_mode = online_mode
	if not online_mode:
		# Offline mode: use Vosk, disable quiz mode
		state_manager.state.active_quiz_mode = False
		state_manager.state.speech_recognizer = 'vosk'
		logger.info("Offline mode: Vosk recognizer enabled, quiz mode disabled.")
	else:
		# Online mode: use Google, enable quiz mode
		state_manager.state.speech_recognizer = 'google'
		logger.info("Online mode: Google recognizer enabled, quiz mode available.")

def main():
	funcButton4.on_tap = lambda: state_manager.toggle_mode()
	threading.Thread(target=volumeControl).start()
	
	while True:
		print("run")
		b = wait_button()
		
		if state_manager.state.main_mode:
			if b == 17:
				EducMode()
			if b == 27:
				print('run detect mode')
		else:
			if b == 17:
				print("wifi connect mode")
			if b == 27:
				print("print barry life")
			# Ensure camera is cleaned up when switching modes
			camera_manager.cleanup()

		# Button 3 handling for education mode
		if not state_manager.state.main_mode and state_manager.state.active_educ_mode:
			if b == 22:  # Button 3
				if not state_manager.state.active_learn_mode and not state_manager.state.active_quiz_mode:
					# First press - enter learn mode
					state_manager.toggle_learning_mode()
					TTS("Entering learning mode. Touch the braille letters to learn them.")
				else:
					# Subsequent presses - toggle between learn and quiz mode
					if state_manager.state.active_learn_mode:
						state_manager.state.active_learn_mode = False
						state_manager.toggle_quiz_mode()
						TTS("Switching to quiz mode. I'll ask you to identify letters.")
					else:
						state_manager.state.active_quiz_mode = False
						state_manager.toggle_learning_mode()
						TTS("Switching to learning mode. Touch the braille letters to learn them.")
		
		time.sleep(0.5)

# QR code login system
def scan_qr_and_login():
	"""Scan a QR code using Picamera2, decode JSON, and set user info in state. Show camera feed with overlays for debugging. Fetch user stats, save to JSON, and print for debugging."""
	global camera_in_use
	from picamera2 import Picamera2
	import cv2
	from pyzbar import pyzbar

	# Wait if camera is in use
	while camera_in_use:
		TTS("Camera is busy. Please wait.")
		time.sleep(1)

	camera_in_use = True
	picam2 = Picamera2()
	config = picam2.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
	picam2.configure(config)
	picam2.start()
	TTS("Please show your QR code to the camera.")
	user_data = None
	try:
		while True:
			frame = picam2.capture_array()
			qrcodes = pyzbar.decode(frame)
			for qr in qrcodes:
				(x, y, w, h) = qr.rect
				cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
				qr_data = qr.data.decode('utf-8')
				cv2.putText(frame, qr_data, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
				try:
					user_data = json.loads(qr_data)
					# Set user info in state
					state_manager.state.current_user_id = user_data.get('id')
					state_manager.state.current_user_email = user_data.get('email')
					state_manager.state.current_user_full_name = user_data.get('full_name')
					TTS(f"Welcome, {state_manager.state.current_user_full_name}. You are now logged in.")
					logger.info(f"User logged in: {user_data}")

					# Fetch user stats from Supabase
					user_id = state_manager.state.current_user_id
					stats = db_manager.get_user_stats(user_id)
					# Save stats to JSON file
					with open('user_stats.json', 'w') as f:
						json.dump(stats, f, indent=2)
					# Print stats for debugging
					print("User stats loaded from Supabase:")
					print(json.dumps(stats, indent=2))

					picam2.stop()
					cv2.destroyAllWindows()
					camera_in_use = False
					return True
				except Exception as e:
					TTS("Invalid QR code. Please try again.")
					logger.error(f"Failed to parse QR code: {e}")
					continue
			# Show camera feed with overlays
			cv2.imshow("Scan QR Code", frame)
			if cv2.waitKey(1) & 0xFF == ord('q'):
				break
	finally:
		try:
			picam2.stop()
		except Exception:
			pass
		cv2.destroyAllWindows()
		camera_in_use = False
	if not user_data:
		TTS("QR code scan cancelled or failed.")
		return False

def logout_user():
	"""Log out the current user and clear user info from state."""
	state_manager.state.current_user_id = None
	state_manager.state.current_user_email = None
	state_manager.state.current_user_full_name = None
	TTS("You have been logged out. Please scan your QR code to log in.")
	logger.info("User logged out.")

# Integrate with Button 2
def setup_button2_login_logout():
	# On tap: scan QR and log in (run in a thread)
	funcButton2.on_tap = lambda: threading.Thread(target=scan_qr_and_login).start()
	# On hold: log out (run in a thread)
	funcButton2.on_hold = lambda: threading.Thread(target=logout_user).start()

# Call this at startup
setup_button2_login_logout()

if __name__ == "__main__":
	initialize_mode()
	main()