from gpiozero import Button
from gpiozero import DigitalOutputDevice
from SystemModules.WifiConnectModule import wifipy
from queue import Queue
import sounddevice as sd
from scipy.io.wavfile import write, read
from scipy.signal import resample
from picamera2 import Picamera2
import RPi.GPIO as GPIO
import time
import threading
import subprocess
import os
import whisper
import numpy as np
import io
import wave
import re
from vosk import Model, KaldiRecognizer
import json


#audioControlModel = whisper.load_model("base")
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"}))

#Button Initialization
button1 = Button(17) #Func 1 button
button2 = Button(27) #Func 2 button
button3 = Button(22) #Func 3 button
button4 = Button(23) #Func 4 button
mainBtn = Button(24, hold_time = 0.1) #Main func button
volUpBtn = Button(6) #Volume up button
volDownBtn = Button(5) #Volume down button

#Vibration Module Initialization
vibrationModule = DigitalOutputDevice(16) #Vibration Module

mainFunctionMode = True

currentVolume = 100
volume = str(currentVolume)

sd.default.device = [0, None]

def wait_button():
    queue = Queue()
    button1.when_pressed = queue.put
    button2.when_pressed = queue.put
    button3.when_pressed = queue.put
    button4.when_pressed = queue.put
    mainBtn.when_pressed = queue.put
    e = queue.get()
    return e.pin.number

def wait_volbutton():
    queue = Queue()
    volUpBtn.when_pressed = queue.put
    volDownBtn.when_pressed = queue.put
    e = queue.get()
    return e.pin.number

def educationMode():
    TTS("Education Mode")
    print("running education mode")
    #mainBtn.when_held = speak
    
def scoreCheckMode():
    TTS("Score Checking Mode")
    print("running score checking mode")

def objectDetectMode():
    TTS("Object Detection Mode")
    print("running object detection mode")
    
def wifiConnectMode():
    TTS("Wifi Connect Mode")
    print("running wifi connectivity mode")
    if wifipy.is_connected:
        print("you are already connected, to change connection press the main button")
        while not button4.is_pressed or button2.is_pressed:
            if mainBtn.is_pressed:
                print("run")
                threading.Thread(target=wifipy.search_for_wifi(button4, picam2)).start()
                break
    else:
        threading.Thread(target=wifipy.search_for_wifi(button4)).start()
    print("Exiting Wifi Connect Mode")
            


def distanceCheckMode():
    TTS("Distance Check Mode")
    print("running distance mode")
    
def batteryCheckMode():
    TTS("Battery Check Mode")
    print("running battery checking mode")

def TTS(text):
    global volume
    threading.Thread(target=lambda: subprocess.run(['espeak-ng', "-a", volume, "-s", "250", "-p", "70", text])).start()
    #subprocess.run(['festival', '--tts'], input=text.encode())

    
def powerOff():
    TTS("Shutting down")
    print("System turning off")
    time.sleep(1.5)
    #os.system('sudo shutdown -h now')
    
    
def toggleFunction():
    global mainFunctionMode
    mainFunctionMode = not mainFunctionMode
    TTS("Main Mode") if mainFunctionMode else TTS("Secondary Mode")
    print("Main Mode" if mainFunctionMode else "Secondary Mode")
    
def vibrate():
    print("vibrating...")
    #vibrationModule.on()
    #time.sleep(1)
    #vibrationModule.off()
    
# def speak():
#     model_path = "/home/ky/AEye/AEyeProj/VoskModels/vosk-model-en-us-0.22"
#     if not os.path.exists(model_path):
#         TTS("Vosk model not found!")
#         print("Please ensure the vosk-model folder is in the project directory.")
#         return
# 
#     model = Model(model_path)
#     recognizer = KaldiRecognizer(model, 16000)
# 
#     fs = 16000
#     audio_data = []
# 
#     TTS("Listening")
# 
#     with sd.InputStream(samplerate=fs, channels=1, dtype='int16') as stream:
#         while mainBtn.is_held:
#             audio_chunk, _ = stream.read(4000)
#             if recognizer.AcceptWaveform(audio_chunk):
#                 result = json.loads(recognizer.Result())
#                 text = result.get("text", "")
#                 if text:
#                     print("Recognized:", text)
#                     TTS(text)
#                     if re.search(r'\bquiz mode\b', text, re.IGNORECASE):
#                         print("Entering quiz mode")
#                         # Add logic to start quiz mode
#                     break
#             else:
#                 partial = json.loads(recognizer.PartialResult()).get("partial", "")
#                 if partial:
#                     print(f"Partial: {partial}", end="\r")
# 
#     print("Done Listening")

# def speak():
#     audio_data = []
#     fs = 44100
#     filename = "output.wav"
#     while mainBtn.is_held:
#         print("Holding")
#         frame = sd.rec(int(0.5 * fs), samplerate=fs, channels=1, dtype='int16')
#         sd.wait()
#         audio_data.append(frame)
# 
#     if audio_data:
#         audio_data = np.concatenate(audio_data, axis=0)
#         write(filename, fs, audio_data)
#         print(f"Saved to {filename}")
#         
#     fs_original, audio = read("output.wav")
#     target_fs = 16000
#     duration = audio.shape[0] / fs_original
#     num_samples = int(duration * target_fs)
#     
#     resampled = resample(audio, num_samples)
#     resampled = np.int16(resampled)
#     
#     write("output.wav", target_fs, resampled)
#         
#     result = audioControlModel.transcribe("output.wav")
#     print("Transcript:", result["text"])
#     
#     if dict_contains_quiz_mode(result):
#         print("Enterng quiz mode")
#         
# def dict_contains_quiz_mode(data):
#     return any(
#         isinstance(value, str) and re.search(r'\bquiz mode\b', value, re.IGNORECASE)
#         for value in data.values()
#     )
def volumeControl():
    print("this is rnning")
    global currentVolume
    global volume
    while True:
        b = wait_volbutton()
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
        time.sleep(0.2)

def main():
    GPIO.cleanup()
    threading.Thread(target=volumeControl).start()
    TTS("A.Eye is now active!")
    print("System Running...")
    wifipy.isActive = False
    lastBut = 0
    button4.when_held = powerOff
    button4.hold_time = 3
    while True:
        b = wait_button()
        if (b != lastBut or b == 23):
            threading.Thread(target=vibrate).start()
        if b == 17 and b != lastBut:
            educationMode() if mainFunctionMode else scoreCheckMode()
        if (b == 27 and b != lastBut):
            objectDetectMode() if mainFunctionMode else wifiConnectMode()
        if b == 22 and b != lastBut:
            distanceCheckMode() if mainFunctionMode else batteryCheckMode()
        if b == 23:
            print("Changing Modes...")
            toggleFunction()
        lastBut = b
        time.sleep(0.5)
        

        

if __name__ == "__main__":
    main()
