######## Webcam Object Detection Using Tensorflow-trained Classifier #########
#
# Author: Dhananjay Khairnnar
# Date: 16/05/2023
# Email: khairnardm@gmail.com
# Country: India
# github: http://www.github.com/8-DK
##############################################################################
#Libraries
import RPi.GPIO as GPIO
import time

PIN_TRIGGER = 4 #7
PIN_ECHO = 17 #11
BTN_PIN = 21

class UltraSonicSensor:
	def __init__(self):
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(PIN_TRIGGER, GPIO.OUT)
		GPIO.setup(PIN_ECHO, GPIO.IN)
		GPIO.output(PIN_TRIGGER, GPIO.LOW)
		time.sleep(2)
		
	def distanceMes(self):
		GPIO.setup(PIN_TRIGGER,GPIO.OUT)
		GPIO.setup(PIN_ECHO,GPIO.IN)
		GPIO.output(PIN_TRIGGER,False)
#time.sleep(0.2)
		GPIO.output(PIN_TRIGGER,GPIO.HIGH)
		time.sleep(0.00001)
		timeOut = time.time()
		pulse_end = pulse_start = time.time()
		#GPIO.output(PIN_ECHO,GPIO.LOW)
		while GPIO.input(PIN_ECHO)==0:
			pulse_start=time.time()
			if(time.time()-timeOut > 2):
				return -1
		while GPIO.input(PIN_ECHO)==1:
			pulse_end=time.time()
			if(time.time()-timeOut > 2):
				return -1
		pulse_duration=pulse_end-pulse_start
		distance=pulse_duration*17150
		distance=round(distance,2)
		return distance
	def testSensor(self):
		while True:
			print("Distance:",self.distanceMes(),"cm")
			time.sleep(0.1)
		
class Button:
	def __init__(self):
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 10 to be an input pin and set 
	
	def readBtn(self):
		time.sleep(0.2)
		if GPIO.input(BTN_PIN) == GPIO.HIGH:
			return "On";
		return "Off";
		
	def testButton(self):
		while True:
			self.readBtn()
			time.sleep(0.1)
