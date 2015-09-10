#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""[Th]ermal [Pr]inter

Usage:
thpr.py [-s | --no-server] [-v | --verbose] [-d | --no-deleting] [-p | --no-printing]
thpr.py (-h | --help)
thpr.py --version

Options:
-h --help           Show this help
--version           Show version
-s --no-server      Do not start Web server
-v --verbose          Enable debug logging
-d --no-deleting   Do not delete mails after printing
-p --no-printing   Do not print anything



Central server to combine several functions around the
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
from PIL import Image, ImageFilter
import socket
from AdafruitThermal import *
import RPi.GPIO as GPIO
import imaplib
import email
from email.header import decode_header
import os
from threading import Timer
import uuid
import shutil
import numpy as np
from docopt import docopt

import logging

logger = logging.getLogger(__name__)


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

class MyThermalPrinter:
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
        self.tp = AdafruitThermal(*args, **kwargs)
        #self.available = False
        # Enable LED and button (w/pull-up on latter)
        self.prev_button_state = GPIO.input(self.button_pin)
        self.prev_time = time.time()
        self.tap_enable = False
        self.hold_enable = False




    def check_network(self):
        # Processor load is heavy at startup; wait a moment to avoid
        # stalling during greeting.
        if self.available:
            time.sleep(0)

        # Show IP address (if network is available)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 0))
            if self.available:
                GPIO.output(self.led_pin, GPIO.HIGH)
                #self.tp.print_line('My IP address is ' + s.getsockname()[0])
                logger.debug('My IP address is ' + s.getsockname()[0])
                #self.tp.feed(3)
                GPIO.output(self.led_pin, GPIO.LOW)
        except:
            if self.available:
                GPIO.output(self.led_pin, GPIO.HIGH)
                self.tp.bold_on()
                self.tp.print_line('Network is unreachable.')
                logger.debug('Network is unreachable.')
                self.tp.bold_off()
                self.tp.print('Connect display and keyboard\n' + \
                              'for network troubleshooting.')
                self.tp.feed(3)
                GPIO.output(self.led_pin, GPIO.LOW)
            exit(0)

    def greeting(self):
        GPIO.output(self.led_pin, GPIO.HIGH)
        # Print greeting image
        if self.available:
            self.tp.print_image(Image.open('gfx/hello.png'), True)
            self.tp.feed(3)
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
    def __init__(self, config, printer, no_deleting=False):
        self.base_dir = os.path.join('/tmp', 'thpr')
        try:
            shutil.rmtree(self.base_dir)
        except:
            pass
        #os.makedirs(self.base_dir)
        self.user = config['EMail']['user']
        self.password = config['EMail']['password']
        self.printer = printer
        self.no_deleting = no_deleting
        
        self.valid_senders = [x[1].lower() for x in config.items('Valid senders')]
        self.valid_recipients = [x[1].lower() for x in config.items('Valid recipients')]
        self.printable_extensions = ['.jpg', '.jpeg', '.png']

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
        relevant_message = False
        message_with_image = False
        to_be_deleted = []        
        for msgId in data[0].split():
            typ, message_parts = imap_session.fetch(msgId, '(RFC822)')
            if typ != 'OK':
                print('Error fetching mail.')
                raise

            email_body = message_parts[0][1]
            mail = email.message_from_string(email_body)
            subject = decode_header(mail['subject'])[0]
            logger.debug('Output from decode header: {0}, encoding {1}'.format(subject[0], subject[1]))
            subject = subject[0]#.decode(subject[1])
            logger.debug('Decoded subject {0}'.format(subject))            
            sender = mail['from']
            recipient = mail['to']
            mail_text = None
            #print('Mail found: subject "{0}", From: {1}, To: {2}'.format(subject, sender, recipient))
            if sender != None and recipient != None:
            
                found_valid_recipient = False
                for val in self.valid_recipients:
                        if recipient.lower().find(val) != -1:
                            found_valid_recipient = True
                        
                found_valid_sender = False
                if sender:
                    for val in self.valid_senders:
                        if sender.lower().find(val) != -1:
                            found_valid_sender = True

                if found_valid_recipient and found_valid_sender:
                    print('Valid mail found: subject "{0}", From: {1}, To: {2}'.format(subject, sender, recipient))
                    if mail.is_multipart():
                        mail_text = None
                        file_name = None
                        for num, part in enumerate(mail.walk()):
                            logger.debug('---'*10)
                            logger.debug('Part No. {0}, Content type: :::{1}:::'.format(num, part.get_content_type()))
                            logger.debug('Part as string')
                            logger.debug(part.as_string()[:100])
                            logger.debug('Part payload')
                            logger.debug(part.get_payload()[:100])

                            if not mail_text and part.get_content_type() == 'text/plain':
                                mail_text = part.get_payload(decode=True).strip(' \n\r')
                                
                                logger.debug('MAILTEXT (Multipart; length: {1}): {0}'.format(mail_text[:100], len(mail_text)))
                            if not file_name:
                                file_name = part.get_filename()
                                if file_name:
                                    logger.debug('Filename: {0}'.format(file_name))
                                    fn, file_extension = os.path.splitext(file_name)
                                    if file_extension.lower() in self.printable_extensions:
                                        message_with_image = True
                                        savedir = os.path.join(self.base_dir, uuid.uuid1().hex)
                                        os.makedirs(savedir)
                                        fp = open(os.path.join(savedir, file_name), 'wb')
                                        fp.write(part.get_payload(decode=True))
                                        fp.close()
                    else:
                        file_name = mail.get_filename()
                        if file_name:
                            logger.debug('Filename: {0}'.format(file_name))
                            fn, file_extension = os.path.splitext(file_name)
                            if file_extension.lower() in self.printable_extensions:
                                message_with_image = True
                                savedir = os.path.join(self.base_dir, uuid.uuid1().hex)
                                os.makedirs(savedir)
                                fp = open(os.path.join(savedir, file_name), 'wb')
                                fp.write(mail.get_payload(decode=True))
                                fp.close()
                        else:
                            mail_text = mail.get_payload(decode=True).strip(' \n\r')
                            logger.debug('MAILTEXT (Singlepart; length: {1}): {0}'.format(mail_text[:100], len(mail_text)))
                    if not message_with_image:
                        self.printer.justify('C')
                        self.printer.print_line(20*'-')
                        self.printer.bold_on()
                        self.printer.print_line(subject)
                        self.printer.bold_off()
                        if mail_text:
                            self.printer.print(mail_text.strip())
                        self.printer.print_line(20*'-')
                        self.printer.justify('L')
                    else:
                        self.printer.justify('C')
                        self.printer.print_line(20*'-')
                        self.printer.bold_on()
                        self.printer.print_line(subject)
                        self.printer.bold_off()
                        if mail_text != None and mail_text != '':
                            self.printer.print_line(mail_text)
                        logger.debug('Directory ({0}) and name ({1})'.format(savedir, file_name))
                        my_image = Image.open(os.path.join(savedir, file_name))
                        new_width = 384
                        percentage = new_width/float(my_image.size[0])
                        new_height = my_image.size[1] * percentage
                        #print('New width {0}, height {1}'.format(int(new_width+0.5), int(new_height+0.5)))
                        gray = my_image.resize([int(new_width+0.5), int(new_height+0.5)]).convert('L')
                        gray_array = np.asarray(gray)
                        #bw = (gray_array > gray_array.mean())*255
                        bw = gray.point(lambda x: 0 if x<np.median(gray_array)*1.1 else 255, '1').convert('1')
                        bw.save(os.path.join('/tmp', 'convert_' + file_name + '.png'))
#                         self.printer.print_image(bw, True)
                        self.printer.print_line(20*'-')
                        self.printer.justify('L')
                    to_be_deleted.append(msgId)
        if to_be_deleted and not self.no_deleting:
            logger.debug('IDs to be moved to trash: {0}'.format(to_be_deleted))
            boxes = imap_session.list()
            #for box in boxes[1]:
            #    print(box)
            for id in to_be_deleted:
                result = imap_session.copy(id, 'Deleted Messages')
                print(result)
                if result[0] == 'OK':
                    imap_session.store(id, '+FLAGS', '\\Deleted')
                    
            imap_session.expunge()
                
        imap_session.close()
        imap_session.logout()        
        

        
                

if __name__ == "__main__":


    # Use Broadcom pin numbers (not Raspberry Pi pin numbers) for GPIO
    arguments = docopt(__doc__, version='thpr.py 0.7')
    ch = logging.StreamHandler()
    
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)

    #print(arguments)
    if arguments['--verbose']:
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        ch.setLevel(logging.INFO)

    # add the handlers to the logger
    logger.addHandler(ch)


    GPIO.setmode(GPIO.BCM)
    config = configparser.ConfigParser()
    config.read('thpr.conf')
    LED_PIN = int(config['Printer']['ledPin'])
    BUTTON_PIN = config['Printer']['buttonPin']
    HOLD_TIME = config['Printer']['timeout_for_hold']     # Duration for button hold (shutdown)


    ACTIONS = PrinterTasks(LED_PIN)
    # Initialization of printer

    PRINTER = MyThermalPrinter(config['Printer']['serial_port'],
                               9600, timeout=5,
                               button_pin = BUTTON_PIN,
                               led_pin = LED_PIN,
                               hold_time = HOLD_TIME,
                               actions = ACTIONS,
                               no_printing = arguments['--no-printing'])
    GPIO.output(LED_PIN, GPIO.HIGH)
    time.sleep(0.5)
    GPIO.output(LED_PIN, GPIO.LOW)

    if not PRINTER.available:
        print('No printer available.')

    
    PRINTER.check_network()
    #PRINTER.greeting()
    
    MR = MailReceiver(config, PRINTER.tp, no_deleting = arguments['--no-deleting'])
    MR.check_mail()
    mail_schedule = Scheduler(60, MR.check_mail)
    #mail_schedule.start()
   
   
    todo_schedule = Scheduler(5, PRINTER.query_button)
    todo_schedule.start()

    if not arguments['--no-server']:
        logger.debug('Starting server')
        webapp.run(host='0.0.0.0', port=80, debug=True, use_reloader=False)
    else:
        logger.debug('Starting endless loop')
        while True:
            pass
    todo_schedule.stop()
    mail_schedule.stop()
