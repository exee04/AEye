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

vibrationModule = DigitalOutputDevice(16) #Vibration Module
mainFunctionMode = True
cooldown = False

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

def function1():
    button1.when_pressed = None
    button2.when_pressed = function2
    button3.when_pressed = function3
    if mainFunctionMode:
        print("run education mode")
    else:
        print("run score check mode")
def function2():
    button1.when_pressed = function1
    button2.when_pressed = None
    button3.when_pressed = function3
    if mainFunctionMode:
        print("run object detection mode")
        #yolo2.startDetection()
    else:
        print("run wifi connectivity mode")
        #wifipy.search_for_wifi()
def function3():
    button1.when_pressed = function1
    button2.when_pressed = function2
    button3.when_pressed = None
    if mainFunctionMode:
        print("run distance mode")
    else:
        print("battery check mode")
    
def function4():
    global cooldown
    if cooldown:
        return  # Ignore if still in cooldown
    cooldown = True
    button1.when_pressed = None
    button2.when_pressed = None
    button3.when_pressed = None
    print("changing modes...")
    toggleFunction()
    def reset_cooldown():
        time.sleep(2)
        global cooldown
        button1.when_pressed = function1
        button2.when_pressed = function2
        button3.when_pressed = function3
        cooldown = False
    threading.Thread(target=reset_cooldown).start()

    
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
    while True:
        b = wait_button()
        if b == 17:
            function1()
        if b == 27:
            function2()
        if b == 22:
            function3()
        if b == 23:
            function4()
        threading.Thread(target=vibrate).start()
        time.sleep(2)
        

if __name__ == "__main__":
    main()