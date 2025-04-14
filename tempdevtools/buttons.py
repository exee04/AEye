from gpiozero import Button
from gpiozero import DigitalOutputDevice
from time import sleep

vibrator = DigitalOutputDevice(16)

button = Button(17)
button.wait_for_press()
print("The button was pressed")
vibrator.on()
sleep(1) 
vibrator.off()

button = Button(27)
button.wait_for_press()
print("The button was pressed")
vibrator.on()
sleep(1)  
vibrator.off()

button = Button(22)
button.wait_for_press()
print("The button was pressed")
vibrator.on()
sleep(1) 
vibrator.off()

button = Button(23)
button.wait_for_press()
print("The button was pressed")
vibrator.on()
sleep(1) 
vibrator.off()

button = Button(24)
button.wait_for_press()
print("The button was pressed")
vibrator.on()
sleep(1) 
vibrator.off()

button = Button(6)
button.wait_for_press()
print("The button was pressed")
vibrator.on()
sleep(1) 
vibrator.off()

button = Button(5)
button.wait_for_press()
print("The button was pressed")
vibrator.on()
sleep(1) 
vibrator.off()
