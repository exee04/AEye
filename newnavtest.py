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
import difflib
import os
import subprocess


def toggleMode():
	global mainMode
	mainMode = not mainMode
	print("Current mode: main mode" if mainMode else "Current mode: secondary mode")

def EducMode():
    print("Education Mode")
    mainBtn.when_held = speak
    global transcript
    global mainMode
    global activeEducMode
    global PROMPT_MAP
    PROMPT_MAP = MAIN_PROMPT_MAP
    activeEducMode = True
    lastTranscript = ""
    funcButton2.on_tap = ScoreCheckMode
    
    TTS("Education Mode")
    while mainMode and activeEducMode:
        if(lastTranscript != lastPrompt):
            lastTranscript = lastPrompt
            print(lastPrompt)
            TTS(lastPrompt)
            CheckForKeywords(lastPrompt)
            if(activeLearnMode):
                pass
            elif(activeQuizMode):
                pass
            
        time.sleep(0.01)
    

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
    best_match = difflib.get_close_matches(prompt, PROMPT_MAP.keys(), n=1, cutoff=threshold)
    return PROMPT_MAP[best_match[0]] if best_match else None

def handle_command(flag):
    global PROMPT_MAP
    if flag == "OBJECT_DETECTION":
        print("running detect mode")
    elif flag == "DISTANCE_CHECK":
        pass
    elif flag == "LEARN_MODE":
        TTS("Entering Learn Mode")
        toggleLearningMode()
    elif flag == "QUIZ_MODE":
        TTS("Entering Quiz Mode")
        toggleQuizMode()
    elif flag == "TIME_QUERY":
        pass
    elif flag == "DATE_QUERY":
        pass
    elif flag == "GREET":
        pass
    elif flag == "CANCEL":
        PROMPT_MAP = MAIN_PROMPT_MAP
    elif flag == "SHOW_HELP":
        pass
    elif flag == "STATE_MODE":
        print(str(PROMPT_MAP))
    else:
        pass

def CheckForKeywords(text):
    command_flag = get_best_match(text)
    if command_flag:
        handle_command(command_flag)
    else:
        TTS("Sorry, I didn’t understand that. Try saying 'help me'.")


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

mainMode = True

#Global variable for checking user prompts
lastPrompt = ""

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
currentVolume = 100
volume = currentVolume

onDefaultLanguage = True
currentLanguage = "en-US"
language1 = "en-US"
language2 = "fil-PH"

activeEducMode = False
activeQuizMode = False
activeLearnMode = False
activeQuestion = False

PROMPT_MAP = None

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