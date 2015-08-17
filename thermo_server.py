## Base from http://mattrichardson.com/Raspberry-Pi-Flask/

import RPi.GPIO as GPIO
from flask import Flask, render_template, request
import configparser
app = Flask(__name__)

GPIO.setmode(GPIO.BCM)

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

if __name__ == "__main__":
   config = configparser.ConfigParser()
   config.read('thermo.conf')
   app.run(host='0.0.0.0', port=80, debug=True)
