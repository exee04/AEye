from gpiozero import Button

class SmartButton:
	def __init__(self, gpio_pin, hold_time = 1, bounce_time = 0.05, on_tap=None, on_hold=None):
		self.button = Button(gpio_pin, hold_time=hold_time, bounce_time=bounce_time)
		self.was_held = False
		self.on_tap = on_tap
		self.on_hold = on_hold
		self.button.when_held = self._handle_hold
		self.button.when_released = self._handle_release
		
	def _handle_hold(self):
		self.was_held = True
		if self.on_hold:
			self.on_hold()  
	def _handle_release(self):
		if not self.was_held and self.on_tap:
			self.on_tap()  
		self.was_held = False  