from gpiozero import Button
from WifiConnectModule import wifipy
import yolo2
import time
import threading

button1 = Button(17)
button2 = Button(27)
button3 = Button(22)
button4 = Button(23)
mainFunctionMode = True
cooldown = False

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
        yolo2.startDetection()
    else:
        print("run wifi connectivity mode")
        wifipy.search_for_wifi()
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
    
def main():
    button1.when_pressed = function1
    button2.when_pressed = function2
    button3.when_pressed = function3
    button4.when_pressed = function4
    print("Test")

if __name__ == "__main__":
    main()