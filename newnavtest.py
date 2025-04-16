import threading
from SystemModules.ButtonModule.SmartButton import SmartButton
import time
from queue import Queue

def toggleMode():
	global mainMode
	mainMode = not mainMode
	print("Current mode: main mode" if mainMode else "Current mode: secondary mode")

def toggleAdvancedSettings():
	global settingsMode
	global functionMode
	functionMode = not functionMode
	settingsMode = not settingsMode
	print("Current mode: Advanced Settings Mode" if settingsMode else "Current mode: Function Mode")


def EducMode():
	stop_event = threading.Event()
	funcButton2.on_tap = lambda: (print("stopping event"), closeEducLoop())
	funcButton4.on_tap = lambda: (closeEducLoop(), toggleMode())
	def closeEducLoop():
		stop_event.set()
	def educLoop():
		while not stop_event.is_set():
			funcButton3.on_tap = lambda: print("quiz mode")
			print("educ mode")
			time.sleep(0.1)
	educLoop()

def wait_button():
	queue = Queue() 
	funcButton1.button.when_pressed = queue.put
	funcButton2.button.when_pressed = queue.put
	funcButton4.button.when_pressed = queue.put
	e = queue.get()
	return e.pin.number



functionMode = True
settingsMode = False
mainMode = True


funcButton1 = SmartButton(17) #button 1
funcButton2 = SmartButton(27) #button 2
funcButton3 = SmartButton(22) #button 3
funcButton4 = SmartButton(23) #button 4
mainBtn = SmartButton(24) #main button
#volUpBtn = SmartButton(6)
#volDownBtn = SmartButton(5)


while True:
	print("run")
	b = wait_button()
	if functionMode:
		if b == 17:
			EducMode() if mainMode else print("score check mode")
		if b == 27:
			print('run detect mode') if mainMode else print("wifi connect")
		funcButton4.on_tap = lambda: (toggleMode())
	elif settingsMode:
		funcButton1.on_tap = lambda: print("shutdown?") if settingsMode else None
		funcButton1.on_hold = lambda: print("restart?") if settingsMode else None
		funcButton2.on_tap = lambda: print("change voice") if settingsMode else None
		funcButton2.on_hold = lambda: print("change voice speed") if settingsMode else None
		funcButton3.on_tap = lambda: print("check battery life") if settingsMode else None
		funcButton4.on_tap = lambda: toggleAdvancedSettings() if settingsMode else toggleMode()
	funcButton4.on_hold = lambda: (toggleAdvancedSettings())
	lastBut = b
	time.sleep(0.5)

