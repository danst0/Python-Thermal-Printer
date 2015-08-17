## Base from http://mattrichardson.com/Raspberry-Pi-Flask/

import RPi.GPIO as GPIO
from flask import Flask, render_template, request
import configparser
app = Flask(__name__)
from __future__ import print_function
import subprocess, time, Image, socket
from Adafruit_Thermal import *

ledPin       = 18
buttonPin    = 23
holdTime     = 2     # Duration for button hold (shutdown)
tapTime      = 0.01  # Debounce time for button taps
nextInterval = 0.0   # Time of next recurring operation
dailyFlag    = False # Set after daily trigger occurs
lastId       = '1'   # State information passed to/from interval script
printer      = Adafruit_Thermal("/dev/ttyAMA0", 19200, timeout=5)



# Create a dictionary called pins to store the pin number, name, and pin state:
pins = {
   24 : {'name' : 'coffee maker', 'state' : GPIO.LOW},
   25 : {'name' : 'lamp', 'state' : GPIO.LOW}
   }

# Set each pin as an output and make it low:
for pin in pins:
   GPIO.setup(pin, GPIO.OUT)
   GPIO.output(pin, GPIO.LOW)

@app.route("/")
def main():
   # For each pin, read the pin state and store it in the pins dictionary:
   for pin in pins:
      pins[pin]['state'] = GPIO.input(pin)
   # Put the pin dictionary into the template data dictionary:
   templateData = {
      'pins' : pins
      }
   # Pass the template data into the template main.html and return it to the user
   return render_template('main.html', **templateData)

# The function below is executed when someone requests a URL with secret_key, action and param
@app.route("/<secret_key>/<action>/<param>")
def action(secret_key, action, param):
   if secret_key == config['api']['secret_key']:
      # key is correct, so continue
      if action == 'print':
         thermo_print(param)
         
   # Along with the pin dictionary, put the message into the template data dictionary:
   templateData = {
      'action' : action,
      'param' : param
   }

   return render_template('main.html', **templateData)


class Scheduler(object):
    def __init__(self, sleep_time, function):
        self.sleep_time = sleep_time
        self.function = function
        self._t = None

    def start(self):
        if self._t is None:
            self._t = Timer(self.sleep_time, self._run)
            self._t.start()
        else:
            raise Exception("this timer is already running")

    def _run(self):
        self.function()
        self._t = Timer(self.sleep_time, self._run)
        self._t.start()

    def stop(self):
        if self._t is not None:
            self._t.cancel()
            self._t = None


def query_button():
   # old init
      # Poll initial button state and time
   prevButtonState = GPIO.input(buttonPin)
   prevTime        = time.time()
   tapEnable       = False
   holdEnable      = False
   
   # Poll current button state and time
   buttonState = GPIO.input(buttonPin)
   t           = time.time()

   # Has button state changed?
   if buttonState != prevButtonState:
      prevButtonState = buttonState   # Yes, save new state/time
      prevTime        = t
   else:                             # Button state unchanged
      if (t - prevTime) >= holdTime:  # Button held more than 'holdTime'?
       # Yes it has.  Is the hold action as-yet untriggered?
      if holdEnable == True:        # Yep!
         hold()                      # Perform hold action (usu. shutdown)
         holdEnable = False          # 1 shot...don't repeat hold action
         tapEnable  = False          # Don't do tap action on release
      elif (t - prevTime) >= tapTime: # Not holdTime.  tapTime elapsed?
         # Yes.  Debounced press or release...
         if buttonState == True:       # Button released?
            if tapEnable == True:       # Ignore if prior hold()
               tap()                     # Tap triggered (button released)
               tapEnable  = False        # Disable tap and hold
               holdEnable = False
         else:                         # Button pressed
            tapEnable  = True           # Enable tap and hold actions
            holdEnable = True

  # LED blinks while idle, for a brief interval every 2 seconds.
  # Pin 18 is PWM-capable and a "sleep throb" would be nice, but
  # the PWM-related library is a hassle for average users to install
  # right now.  Might return to this later when it's more accessible.
   if ((int(t) & 1) == 0) and ((t - int(t)) < 0.15):
      GPIO.output(ledPin, GPIO.HIGH)
   else:
      GPIO.output(ledPin, GPIO.LOW)

   # Once per day (currently set for 6:30am local time, or when script
   # is first run, if after 6:30am), run forecast and sudoku scripts.
   l = time.localtime()
   if (60 * l.tm_hour + l.tm_min) > (60 * 6 + 30):
      if dailyFlag == False:
         daily()
         dailyFlag = True
   else:
      dailyFlag = False  # Reset daily trigger


if __name__ == "__main__":
   config = configparser.ConfigParser()
   config.read('thermo.conf')
   
   # Initialization of printer

   # Use Broadcom pin numbers (not Raspberry Pi pin numbers) for GPIO
   GPIO.setmode(GPIO.BCM)

   # Enable LED and button (w/pull-up on latter)
   GPIO.setup(ledPin, GPIO.OUT)
   GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

   # LED on while working
   GPIO.output(ledPin, GPIO.HIGH)

   # Processor load is heavy at startup; wait a moment to avoid
   # stalling during greeting.
   time.sleep(30)

   # Show IP address (if network is available)
   try:
	   s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	   s.connect(('8.8.8.8', 0))
   	printer.print('My IP address is ' + s.getsockname()[0])
	   printer.feed(3)
   except:
   	printer.boldOn()
	   printer.println('Network is unreachable.')
   	printer.boldOff()
   	printer.print('Connect display and keyboard\n'
   	  'for network troubleshooting.')
   	printer.feed(3)
   	exit(0)

   # Print greeting image
   printer.printImage(Image.open('gfx/hello.png'), True)
   printer.feed(3)
   GPIO.output(ledPin, GPIO.LOW)



   
   scheduler = Scheduler(5, query_button)
   scheduler.start()
   app.run(host='0.0.0.0', port=80, debug=True)
   scheduler.stop()
