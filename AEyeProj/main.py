from gpiozero import Button
from gpiozero import DigitalOutputDevice
from WifiConnectModule import wifipy
from queue import Queue
import RPi.GPIO as GPIO
import time
import threading
import subprocess

#Button Initialization
GPIO.cleanup()
button1 = Button(17) #Func 1 button
button2 = Button(27) #Func 2 button
button3 = Button(22) #Func 3 button
button4 = Button(23) #Func 4 button
mainBtn = Button(24) #Main func button
volUpBtn = Button(6) #Volume up button
volDownBtn = Button(5) #Volume down button

#Vibration Module Initialization
vibrationModule = DigitalOutputDevice(16) #Vibration Module

mainFunctionMode = True

currentVolume = 100
volume = str(currentVolume)

def wait_button():
    queue = Queue()
    button1.when_pressed = queue.put
    button2.when_pressed = queue.put
    button3.when_pressed = queue.put
    button4.when_pressed = queue.put
    mainBtn.when_pressed = queue.put
    volUpBtn.when_pressed = queue.put
    volDownBtn.when_pressed = queue.put
    e = queue.get()
    return e.pin.number

def educationMode():
    TTS("Education Mode")
    print("running education mode")
    
def scoreCheckMode():
    TTS("Score Checking Mode")
    print("running score checking mode")

def objectDetectMode():
    TTS("Object Detection Mode")
    print("running object detection mode")
    
def wifiConnectMode():
    TTS("Wifi Connect Mode")
    print("running wifi connectivity mode")

def distanceCheckMode():
    TTS("Distance Check Mode")
    print("running distance mode")
    
def batteryCheckMode():
    TTS("Battery Check Mode")
    print("running battery checking mode")

def TTS(text):
    global volume
    subprocess.run(['espeak-ng', "-a", volume, "-s", "250", "-p", "70", text])
    #subprocess.run(['festival', '--tts'], input=text.encode())

    
def toggleFunction():
    TTS("Changing Mode")
    global mainFunctionMode
    mainFunctionMode = not mainFunctionMode
    TTS("Main Mode") if mainFunctionMode else TTS("Secondary Mode")
    print("Main Mode" if mainFunctionMode else "Secondary Mode")
    
def vibrate():
    print("vibrating...")
    vibrationModule.on()
    time.sleep(0.3)
    vibrationModule.off()
    
    
        

def main():
    GPIO.cleanup()
    global currentVolume
    print("System Running...")
    lastBut = 0
    while True:
        b = wait_button()
        if (b != lastBut or b == 23) and (b != 6 and b != 5):
            threading.Thread(target=vibrate).start()
        if b == 17 and b != lastBut:
            educationMode() if mainFunctionMode else scoreCheckMode()
        if b == 27 and b != lastBut:
            objectDetectMode() if mainFunctionMode else wifiConnectMode()
        if b == 22 and b != lastBut:
            distanceCheckMode() if mainFunctionMode else batteryCheckMode()
        if b == 23:
            print("Changing Modes...")
            toggleFunction()
        if b == 6:
            print("Increasing Volume")
            TTS("Volume Up") if (currentVolume != 200) else TTS("Max Volume")
            currentVolume = (currentVolume + 20) if (currentVolume != 200) else currentVolume
        if b == 5:
            print("Decreasing Volume")
            TTS("Volume Down") if (currentVolume != 0) else TTS("No Volume")
            currentVolume = (currentVolume - 20) if (currentVolume != 0) else currentVolume

        lastBut = b
        global volume
        volume = str(currentVolume)
        print(volume)
        time.sleep(0) if (b == 6 or b == 5) else time.sleep(1)
        

        

if __name__ == "__main__":
    main()