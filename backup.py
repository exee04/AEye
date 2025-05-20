import threading
from SystemModules.ButtonModule.SmartButton import SmartButton
import time
from queue import Queue
from gpiozero import Button
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

def toggleMode():
	global mainMode
	mainMode = not mainMode
	print("Current mode: main mode" if mainMode else "Current mode: secondary mode")

def EducMode():
    print("Education Mode")
    mainBtn.when_held = lambda: threading.Thread(target=speak).start()
    global transcript
    global lastPrompt
    global mainMode
    global activeEducMode
    global PROMPT_MAP
    PROMPT_MAP = MAIN_PROMPT_MAP
    activeEducMode = True
    lastTranscript = ""
    funcButton2.on_tap = ScoreCheckMode
    answer = ""

    global marker_corners, braille_positions

    braille_scanned = False
    base_marker_center = None
    last_scan_time = 0
    cooldown_duration = 5  # seconds

    picam2 = Picamera2()
    config = picam2.create_still_configuration(main={"format": "RGB888", "size": (640, 480)})
    picam2.configure(config)
    picam2.start()
    time.sleep(1)
    center_history = []
    
    TTS("Education Mode")
    while mainMode and activeEducMode:
        if((lastTranscript != lastPrompt) and not activeQuizMode):
            lastTranscript = lastPrompt
            print(lastPrompt)
            CheckForKeywords(lastPrompt)
        frame = picam2.capture_array()
        if frame is None:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        parameters = cv2.aruco.DetectorParameters()
        aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
        corners, ids, _ = aruco_detector.detectMarkers(gray)

        current_time = time.time()
        if ids is not None and 1 in ids:
            idx = list(ids).index(1)
            marker_corners = corners[idx][0]
            current_marker_center = (
                int((marker_corners[0][0] + marker_corners[2][0]) / 2),
                int((marker_corners[0][1] + marker_corners[2][1]) / 2)
            )
            cv2.circle(frame, current_marker_center, 5, (255, 0, 0), -1)
            center_history.append(current_marker_center)
            if len(center_history) > 15:
                center_history.pop(0)

            if not braille_scanned and is_stable(center_history, max_variance=20) and (current_time - last_scan_time > cooldown_duration):
                base_marker_center = current_marker_center
                blurred = cv2.GaussianBlur(frame, (3, 3), sigmaX=1)
                _, thresholded = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY)
                results = yolo_model(thresholded)[0]
                braille_positions.clear()

                for box in results.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    label = results.names[int(box.cls)]
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)

                    rel_x = cx - base_marker_center[0]
                    rel_y = cy - base_marker_center[1]

                    braille_positions.append({
                        "label": label,
                        "relative": (rel_x, rel_y),
                        "size": (x2 - x1, y2 - y1)
                    })

                braille_scanned = True
                last_scan_time = current_time
                print("✅ Braille scanned. Starting cooldown...")

        else:
            if current_time - last_scan_time > cooldown_duration:
                braille_scanned = False  # Only allow rescan after cooldown

        # Draw stored Braille positions
        if marker_corners is not None:
            for braille in braille_positions:
                rel_x, rel_y = braille["relative"]
                label = braille["label"]
                box_w, box_h = braille["size"]

                abs_x = current_marker_center[0] + rel_x
                abs_y = current_marker_center[1] + rel_y

                top_left = (int(abs_x - box_w / 2), int(abs_y - box_h / 2))
                bottom_right = (int(abs_x + box_w / 2), int(abs_y + box_h / 2))

                cv2.rectangle(frame, top_left, bottom_right, (0, 255, 0), 2)
                cv2.putText(frame, label, (top_left[0], top_left[1] - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Finger detection
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        result = hands.process(frame_bgr)

        if result.multi_hand_landmarks:
            for handLms in result.multi_hand_landmarks:
                h, w, _ = frame.shape
                fingertip = handLms.landmark[8]
                fx, fy = int(fingertip.x * w), int(fingertip.y * h)

                for braille in braille_positions:
                    rel_x, rel_y = braille["relative"]
                    abs_x = current_marker_center[0] + rel_x
                    abs_y = current_marker_center[1] + rel_y

                    if abs(fx - abs_x) < 30 and abs(fy - abs_y) < 30:
                            currentBrailleLetter = braille['label']
                            if(activeLearnMode):
                                TTS(f"You are touching letter {currentBrailleLetter}")
                                time.sleep(2)
                                break
                            elif activeQuizMode:
                                run_quiz_question(currentBrailleLetter, lastTranscript, lastPrompt)
                                break
                                
                                
                      

        cv2.imshow("frame", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        
    picam2.stop()
    time.sleep(0.01)
    
def run_quiz_question(currentBrailleLetter, lastTranscript, lastPrompt):
    correct_letter = currentBrailleLetter.upper()
    print("What letter is this?")
    TTS("What letter is this?")

    while True:
        if lastTranscript != lastPrompt and lastTranscript.strip() != "":
            user_input = lastTranscript
            lastPrompt = lastTranscript  # Update to avoid repeating

            extracted = extract_letter_answer(user_input)

            if extracted:
                print(f"User answered: {extracted}")
                if extracted == correct_letter:
                    print("Correct!")
                    TTS("Correct!")
                    # Add scoring logic here in the future
                else:
                    print(f"Wrong. The correct answer was {correct_letter}")
                    TTS(f"Wrong. The correct answer was {correct_letter}")
                    # Add scoring logic here in the future
                break
            else:
                print("Sorry, I didn’t catch that. Please say the letter again.")
                TTS("Sorry, I didn’t catch that. Please say the letter again.")
                
def ScoreCheckMode():
    global activeEducMode
    activeEducMode = False

def toggleLearningMode():
    global activeLearnMode
    global PROMPT_MAP
    PROMPT_MAP = EDUCATION_PROMPT_MAP
    activeLearnMode = not activeLearnMode
    print("Learn Mode = " + str(activeLearnMode))

def toggleQuizMode():
    global activeQuizMode
    global PROMPT_MAP
    PROMPT_MAP = QUIZ_PROMPT_MAP
    activeQuizMode = not activeQuizMode
    print("Quiz Mode =" + str(activeQuizMode))

def toggleQuestionMode():
    global activeQuestion
    activeQuestion = not activeQuestion

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

def vibrate():
    print("vibrating...")
    #vibrationModule.on()
    #time.sleep(1)
    #vibrationModule.off()

def TTS(text):
    global volume
    global voiceSpeed
    threading.Thread(target=lambda: subprocess.run(['espeak-ng', "-a", str(volume), "-s", str(voiceSpeed), "-p", "70", text])).start()
    #subprocess.run(['festival', '--tts'], input=text.encode())

def speak():
    global lastPrompt                                                                            
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

    # Google Speech-to-Text
    with open(filename, "rb") as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)

    try:
        response = client.recognize(config=config, audio=audio)
        for result in response.results:
            transcript = result.alternatives[0].transcript
            print("Transcript:", transcript)
        lastPrompt = transcript

    except Exception as e:
        print("Google transcription error:", e)

    # Clean up
    if os.path.exists(filename):
        os.remove(filename)

def changeLanguage():
    global onDefaultLanguage
    global currentLanguage
    onDefaultLanguage = not onDefaultLanguage 
    currentLanguage = "en-US" if onDefaultLanguage else "fil-PH"
	
def changeTalkingSpeed():
    global onVolumeControl
    onVolumeControl = not onVolumeControl

def volumeControl():
    print("this is rnning")
    global currentVolume
    global volume
    global onVolumeControl
    global voiceSpeed
    MIN_SPEED = 100
    MAX_SPEED = 280
    RATE = 10
    while True:
        b = wait_volbutton()
        if onVolumeControl:
            if b == 6:
                print("Increasing Volume")
                TTS("Volume Up") if (currentVolume != 200) else TTS("Max Volume")
                currentVolume = (currentVolume + 20) if (currentVolume != 200) else currentVolume
                volume = str(currentVolume)
                print(volume)
            if b == 5:
                print("Decreasing Volume")
                TTS("Volume Down") if (currentVolume != 0) else TTS("No Volume")
                currentVolume = (currentVolume - 20) if (currentVolume != 0) else currentVolume
        
                volume = str(currentVolume)
                print(volume)
        else:
            if b == 6:
                if voiceSpeed + RATE <= MAX_SPEED:
                    voiceSpeed += RATE
                    print(f"Increasing Talking Speed to {voiceSpeed} WPM")
                    TTS("Increasing Talking Speed")
                else:
                    print(f"Already at Max Speed ({MAX_SPEED} WPM)")
                    TTS("Max Talking Speed")

            if b == 5:
                if voiceSpeed - RATE >= MIN_SPEED:
                    voiceSpeed -= RATE
                    print(f"Decreasing Talking Speed to {voiceSpeed} WPM")
                    TTS("Decreasing Talking Speed")
                else:
                    print(f"Already at Min Speed ({MIN_SPEED} WPM)")
                    TTS("Minimun Talking Speed")
        time.sleep(0.2)

def get_best_match(prompt: str, threshold=0.65):
    global PROMPT_MAP
    prompt = prompt.lower()
    PROMPT_MAP_AND_COMMON_MAP = {**PROMPT_MAP, **COMMON_PROMPT_MAP}
    best_match = difflib.get_close_matches(prompt, PROMPT_MAP_AND_COMMON_MAP.keys(), n=1, cutoff=threshold)
    print(best_match)
    return PROMPT_MAP_AND_COMMON_MAP[best_match[0]] if best_match else None

def handle_command(flag):
    match flag:
        case "LEARN_MODE":
            toggleLearningMode()
        case "QUIZ_MODE":
            toggleQuizMode()
        case "OBJECT_DETECTION":
            pass
        case "DISTANCE_CHECK":
            pass
        case "DESCRIBE_LETTER":
            pass
        case "REPEAT_DESCRIPTION":
            pass
        case "ANSWER":
            pass
        case "DENY":
            pass
        case "GREET":
            Greetings()
        case "STATE_MODE":
            print(str(PROMPT_MAP))
            pass
        case "TIME_QUERY":
            TimeQuery()
        case "DATE_QUERY":
            DateQuery()

def CheckForKeywords(text):
    command_flag = get_best_match(text)
    if command_flag:
        handle_command(command_flag)
    else:
        TTS("Sorry, I didn’t understand that. Try saying 'help me'.")


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
hands = mp.solutions.hands.Hands(
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

def main():
    funcButton4.on_tap = lambda: toggleMode()
    threading.Thread(target=volumeControl).start()
    
    while True:
        print("run")
        b = wait_button()
        
        if mainMode:
            if b == 17:
                EducMode()
            if b == 27:
                print('run detect mode')
        else:
            if b == 17:
                print("wifi connect mode")
            if b == 27:
                print("print barry life")

        funcButton3.on_hold = lambda: changeLanguage()
        funcButton3.on_tap = lambda: changeTalkingSpeed()
        
        lastBut = b
        time.sleep(0.5)

if __name__ == "__main__":
     main()