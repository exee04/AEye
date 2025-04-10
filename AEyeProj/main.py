from gpiozero import Button
from gpiozero import DigitalOutputDevice
from WifiConnectModule import wifipy
from queue import Queue
import yolo2
import time
import threading

#Button Initialization
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
    print("running education mode")
    
def scoreCheckMode():
    print("running score checking mode")

def objectDetectMode():
    print("running object detection mode")
    
def wifiConnectMode():
    print("running wifi connectivity mode")

def distanceCheckMode():
    print("running distance mode")
    
def batteryCheckMode():
    print("running battery checking mode")

    
def toggleFunction():
    global mainFunctionMode
    mainFunctionMode = not mainFunctionMode
    print("Main Mode" if mainFunctionMode else "Secondary Mode")
    
def vibrate():
    vibrationModule.on()
    time.sleep(0.5)
    vibrationModule.off()

def main():
    print("System Running...")
    lastBut = 0
    while True:
        b = wait_button()
        if b == 17 and b != lastBut:
            educationMode() if mainFunctionMode else scoreCheckMode()
        if b == 27 and b != lastBut:
            objectDetectMode() if mainFunctionMode else wifiConnectMode()
        if b == 22 and b != lastBut:
            distanceCheckMode() if mainFunctionMode else batteryCheckMode()
        if b == 23:
            print("Changing Modes...")
            toggleFunction()
        if b != lastBut or b == 23:
            threading.Thread(target=vibrate).start()
        lastBut = b
        time.sleep(2)

        

if __name__ == "__main__":
    main()