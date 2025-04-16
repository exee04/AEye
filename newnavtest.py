import threading
from SystemModules.ButtonModule.SmartButton import SmartButton
import time
from queue import Queue
from gpiozero import Button
from google.cloud import speech
import sounddevice as sd
import numpy as np
from scipy.signal import resample_poly
from scipy.io.wavfile import write, read
import os
import subprocess


def toggleMode():
	global mainMode
	mainMode = not mainMode
	print("Current mode: main mode" if mainMode else "Current mode: secondary mode")

def EducMode():
	mainBtn.when_held = speak
	global transcript
	lastTranscript = ""
	while True:
		if lastTranscript != lastPrompt:
			print("new command has been said")
			lastTranscript = lastPrompt

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
    threading.Thread(target=lambda: subprocess.run(['espeak-ng', "-a", volume, "-s", voiceSpeed, "-p", "70", text])).start()
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
    MIN_SPEED = 80
    MAX_SPEED = 250
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
                if voiceSpeed + 10 <= MAX_SPEED:
                    voiceSpeed += 10
                    print(f"Increasing Talking Speed to {voiceSpeed} WPM")
            else:
                print(f"Already at Max Speed ({MAX_SPEED} WPM)")

            if b == 5:
                if voiceSpeed - 10 >= MIN_SPEED:
                    voiceSpeed -= 10
                    print(f"Decreasing Talking Speed to {voiceSpeed} WPM")
            else:
                print(f"Already at Min Speed ({MIN_SPEED} WPM)")
        time.sleep(0.2)


client = speech.SpeechClient() #Google API Client

#Microphone Initialization
fs = 44100  
target_fs = 16000  
filename = "output.wav"
config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=target_fs,
        language_code="en-US",
		alternative_language_codes="fil-PH",
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
#volUpBtn = SmartButton(6)
#volDownBtn = SmartButton(5)

onVolumeControl = True

voiceSpeed = 175

onDefaultLanguage = True
currentLanguage = "en-US"
language1 = "en-US"
language2 = "fil-PH"

funcButton4.on_tap = lambda: (toggleMode())
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

