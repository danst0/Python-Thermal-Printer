#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Central server to combine several functions around the
Thermal Printer.
1) Server to receive tasks by IfThisThanThat (ifttt.com), requires
a internet connection and publicly available domain.

2) Controller over the Thermal Printer hardware (together with
Adafruit_Thermal) and one additional button and one LED

3) Scheduler to execute regular prints, e.g. for updates for important
mails, RSS-feeds, tweets (controlled by a config file)

Credits:
Original version based on 
* http://mattrichardson.com/Raspberry-Pi-Flask/,
* main.py from Adafruit ThermalPrinter on GitHub,
* MailReceiver, http://stackoverflow.com/questions/8307809/save-email-attachment-python3-pop3-ssl-gmail, https://gist.github.com/vwillcox/5090214, https://gist.github.com/baali/2633554
"""

from __future__ import print_function
from flask import Flask, render_template, request
import configparser
import subprocess
import time
from PIL import Image
import socket
from Adafruit_Thermal import *
import RPi.GPIO as GPIO
import imaplib
import email
import os
from threading import Timer



lastId = '1'   # State information passed to/from interval script
webapp = Flask(__name__)


    
@webapp.route("/")
def main():
    # For each pin, read the pin state and store it in the pins dictionary:
    #for pin in pins:
    #    pins[pin]['state'] = GPIO.input(pin)
    # Put the pin dictionary into the template data dictionary:
    #templateData = {'pins': pins}
    # Pass the template data into the template main.html and
    # return it to the user
    return render_template('main.html')#, **templateData)

@webapp.route("/<secret_key>/<action>/<param>")
def action(secret_key, action, param):
    """Executed when someone requests a URL with secret_key, action and param"""
    if secret_key == config['api']['secret_key']:
        # key is correct, so continue
        if action == 'print':
            pass
            print('Here I would do something')
            #thermo_print(param)
         
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

class PrinterTasks():
    
    def __init__(self, led_pin):
        self.led_pin = led_pin
    
    def tap(self):
        """Called when button is briefly tapped.  Invokes time/temperature script."""
        GPIO.output(self.led_pin, GPIO.HIGH)  # LED on while working
        subprocess.call(["python", "timetemp.py"])
        GPIO.output(self.led_pin, GPIO.LOW)

    def hold(self):
        """Called when button is held down.  Prints image, invokes shutdown process."""
        GPIO.output(self.led_pin, GPIO.HIGH)
        printer.printImage(Image.open('gfx/goodbye.png'), True)
        printer.feed(3)
        subprocess.call("sync")
        subprocess.call(["shutdown", "-h", "now"])
        GPIO.output(self.led_pin, GPIO.LOW)

    
    def interval(self):
        """Called at periodic intervals (30 seconds by default).
            Invokes twitter script.
        """
        GPIO.output(self.led_pin, GPIO.HIGH)
        p = subprocess.Popen(["python", "twitter.py", str(lastId)],
                stdout=subprocess.PIPE)
        GPIO.output(self.led_pin, GPIO.LOW)
        return p.communicate()[0] # Script pipes back lastId, returned to main


    
    def daily(self):
        """ Called once per day (6:30am by default).
        
            Invokes weather forecast and sudoku-gfx scripts.
        """
        GPIO.output(self.led_pin, GPIO.HIGH)
        subprocess.call(["python", "forecast.py"])
        subprocess.call(["python", "sudoku-gfx.py"])
        GPIO.output(self.led_pin, GPIO.LOW)

class MyThermalPrinter(Adafruit_Thermal):
    """Thermal Printer class with added button and LED"""

    # Poll initial button state and time

    def __init__(self, *args, **kwargs):
        self.button_pin = int(kwargs.pop('button_pin'))
        self.led_pin = int(kwargs.pop('led_pin'))
        self.actions = kwargs.pop('actions')
        self.hold_time = int(kwargs.pop('hold_time'))
        self.available = True
        self.tap_time = 0.01  # Debounce time for button taps
        self.next_interval = 0.0   # Time of next recurring operation
        self.daily_flag = False  # Set after daily trigger occurs
        GPIO.setup(self.led_pin, GPIO.OUT)
        GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        try:
            super().__init__(*args, **kwargs)
        except:
            self.available = False
        # Enable LED and button (w/pull-up on latter)
        self.prev_button_state = GPIO.input(self.button_pin)
        self.prev_time = time.time()
        self.tap_enable = False
        self.hold_enable = False




    def check_network(self):
        # Processor load is heavy at startup; wait a moment to avoid
        # stalling during greeting.
        if self.available:
            time.sleep(30)

        # Show IP address (if network is available)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 0))
            if self.available:
                GPIO.output(self.led_pin, GPIO.HIGH)
                printer.print('My IP address is ' + s.getsockname()[0])
                print('My IP address is ' + s.getsockname()[0])
                printer.feed(3)
                GPIO.output(self.led_pin, GPIO.LOW)
        except:
            if self.available:
                GPIO.output(self.led_pin, GPIO.HIGH)
                printer.bold_on()
                printer.print_line('Network is unreachable.')
                print('Network is unreachable.')
                printer.bold_off()
                printer.print('Connect display and keyboard\n' + \
                              'for network troubleshooting.')
                printer.feed(3)
                GPIO.output(self.led_pin, GPIO.LOW)
            exit(0)

    def greeting(self):
        GPIO.output(self.led_pin, GPIO.HIGH)
        # Print greeting image
        if self.available:
            printer.print_image(Image.open('gfx/hello.png'), True)
            printer.feed(3)
        GPIO.output(self.led_pin, GPIO.LOW)

    def query_button(self):
        # Poll current button state and time
        button_state = GPIO.input(self.button_pin)
        t = time.time()

        # Has button state changed?
        if button_state != self.prev_button_state:
            self.prev_button_state = button_state   # Yes, save new state/time
            self.prev_time = t
        else:                             # Button state unchanged
            if (t - self.prev_time) >= self.hold_time:  # Button held more than 'holdTime'?
                # Yes it has.  Is the hold action as-yet untriggered?
                if self.hold_enable == True:        # Yep!
                    self.actions.hold()                      # Perform hold action (usu. shutdown)
                    self.hold_enable = False          # 1 shot...don't repeat hold action
                    self.tap_enable  = False          # Don't do tap action on release
            elif (t - self.prev_time) >= self.tap_time: # Not holdTime.  tapTime elapsed?
                # Yes.  Debounced press or release...
                if button_state == True:       # Button released?
                    if self.tap_enable == True:       # Ignore if prior hold()
                        self.actions.tap()                     # Tap triggered (button released)
                        self.hold_enable = False
                else:                         # Button pressed
                    self.tap_enable  = True           # Enable tap and hold actions
                    self.hold_enable = True

        # LED blinks while idle, for a brief interval every 2 seconds.
        # Pin 18 is PWM-capable and a "sleep throb" would be nice, but
        # the PWM-related library is a hassle for average users to install
        # right now.  Might return to this later when it's more accessible.
        if ((int(t) & 1) == 0) and ((t - int(t)) < 0.15):
            GPIO.output(self.led_pin, GPIO.HIGH)
        else:
            GPIO.output(self.led_pin, GPIO.LOW)

        # Once per day (currently set for 6:30am local time, or when script
        # is first run, if after 6:30am), run forecast and sudoku scripts.
        loc_time = time.localtime()
        if loc_time.tm_hour ==  6 and loc_time.tm_min == 30:
            if self.daily_flag == False:
                self.actions.daily()
                self.daily_flag = True
        else:
            self.daily_flag = False  # Reset daily trigger


class MailReceiver(object):
    def __init__(self, user, password, printer):
        self.savedir="/tmp"
        self.user = user
        self.password = password
        self.printer = printer
        self.valid_senders = ['daniel@dumke.me']

    def check_mail(self):
        # Icloud mail
        # Benutzername: Dies ist in der Regel der Namensteil Ihrer
        # iCloud-E-Mail-Adresse (beispielsweise emilyparker, nicht
        # emilyparker@icloud.com). Wenn Ihr E-Mail-Client bei Verwendung
        # des Namensteils Ihrer iCloud-E-Mail-Adresse keine Verbindung zu 
        # iCloud herstellen kann, probieren Sie, die vollständige Adresse
        # zu verwenden.
        # Kennwort: Ihr iCloud-Kennwort (app specific!!!)
        imap_session = imaplib.IMAP4_SSL('imap.mail.me.com', 993)
        imap_session.login(self.user, self.password)
        imap_session.select('inbox')
        
        
        typ, data = imap_session.search(None, 'ALL')
        if typ != 'OK':
            print('Error searching Inbox.')
            raise
    
        # Iterating over all emails
        for msgId in data[0].split():
            typ, message_parts = imap_session.fetch(msgId, '(RFC822)')
            if typ != 'OK':
                print('Error fetching mail.')
                raise

            email_body = message_parts[0][1]
            mail = email.message_from_string(email_body)
            subject = mail['subject']
            sender = mail['from']
            sender = sender.replace('<','')
            sender = sender.replace('>','')
            found_valid_sender = False
            for val in self.valid_senders:
                if sender.find(val) != -1:
                    found_valid_sender = True
            if found_valid_sender:
                print('Subject {0}, From: {1}'.format(subject, sender))
                for part in mail.walk():
                    if part.get_content_maintype() == 'multipart':
                        # print part.as_string()
                        continue
                    if part.get('Content-Disposition') is None:
                        # print part.as_string()
                        continue
                    file_name = part.get_filename()

                    if file_name:
                        print(file_name)
                        fp = open(os.path.join(self.savedir, file_name), 'wb')
                        fp.write(part.get_payload(decode=True))
                        fp.close()
        #mail.expunge()
          
        imap_session.close()
        imap_session.logout()
        
        

 
        if message_no_image:
            self.printer.bold_on()
            self.printer.print_line(subject_line)
            self.printer.bold_off()
            if mail_text:
                self.printer.print(mail_text)
        elif message_with_image:
            self.printer.bold_on()
            self.printer.print_line(subject_line)
            self.printer.bold_off()
            self.printer.print(mail_text)
            my_image = Image.open(os.path.join(self.savedir, filename))
            new_width = 384
            percentage = new_width/float(my_image.size[0])
            new_height = my_image.size[1] * percentage
            my_image = my_image.resize( [new_width, new_height] )
            self.printer.print_image(my_image, True)
                

if __name__ == "__main__":
    # Use Broadcom pin numbers (not Raspberry Pi pin numbers) for GPIO
    GPIO.setmode(GPIO.BCM)
    config = configparser.ConfigParser()
    config.read('thpr.conf')
    LED_PIN = config['Printer']['ledPin']
    BUTTON_PIN = config['Printer']['buttonPin']
    HOLD_TIME = config['Printer']['timeout_for_hold']     # Duration for button hold (shutdown)

    ACTIONS = PrinterTasks(LED_PIN)
    # Initialization of printer

    PRINTER = MyThermalPrinter(config['Printer']['serial_port'],
                               19200, timeout=5,
                               button_pin = BUTTON_PIN,
                               led_pin = LED_PIN,
                               hold_time = HOLD_TIME,
                               actions = ACTIONS)
    if not PRINTER.available:
        print('No printer available.')

    
    PRINTER.check_network()
    PRINTER.greeting()
    
    MR = MailReceiver(config['EMail']['user'],
                      config['EMail']['password'], PRINTER)
    mail_schedule = Scheduler(30, MR.check_mail)
    mail_schedule.start()
   
   
    todo_schedule = Scheduler(5, PRINTER.query_button)
    todo_schedule.start()
    webapp.run(host='0.0.0.0', port=80, debug=True)
    todo_schedule.stop()
    mail_schedule.stop()