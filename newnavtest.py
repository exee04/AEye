from gpiozero import Button
import time

class SmartButton:
	def __init__(self, gpio_pin, hold_time = 2, bounce_time = 0.05, on_tap=None, on_hold=None):
		self.button = Button(gpio_pin, hold_time=hold_time, bounce_time=bounce_time)
		self.was_held = False
		self.on_tap = on_tap
		self.on_hold = on_hold
		
		self.button.when_held = self._handle_hold
		self.button.when_released = self._handle_release
		
	def _handle_hold(self):
		self.was_held = True
		if self.on_hold:
			self.on_hold()  # Run hold action immediately

	def _handle_release(self):
		if not self.was_held and self.on_tap:
			self.on_tap()  # Only run tap if it wasn't held
		self.was_held = False  # Reset
				
	

# button2 = Button(27) #Func 2 button
# button3 = Button(22) #Func 3 button
# button4 = Button(23) #Func 4 button
# mainBtn = Button(24, hold_time = 0.1) #Main func button
# volUpBtn = Button(6) #Volume up button
# volDownBtn = Button(5) #Volume down button



smart_button1 = SmartButton(17, hold_time=1, on_tap=lambda: print("tapped"), on_hold=lambda: print("held"))

while True:
	print(smart_button1.button.is_held)
	time.sleep(0.1)


