#!/usr/local/bin/python

from AdafruitThermal import *

printer = AdafruitThermal("/dev/cu.usbserial-AH02DXOC", 9600, timeout=5)



# Test inverse on & off
printer.inverse_on()
printer.print_line("Inverse ON")
printer.inverse_off()

# Test character double-height on & off
printer.double_height_on()
printer.print_line("Double Height ON")
printer.double_height_off()

# Set justification (right, center, left) -- accepts 'L', 'C', 'R'
printer.justify('R')
printer.print_line("Right justified")
printer.justify('C')
printer.print_line("Center justified")
printer.justify('L')
printer.print_line("Left justified")

# Test more styles
printer.bold_on()
printer.print_line("Bold text")
printer.bold_off()

printer.underline_on()
printer.print_line("Underlined text")
printer.underline_off()

printer.set_size('L')   # Set type size, accepts 'S', 'M', 'L'
printer.print_line("Large")
printer.set_size('M')
printer.print_line("Medium")
printer.set_size('S')
printer.print_line("Small")

printer.justify('C')
printer.print_line("normal\nline\nspacing")
printer.set_line_height(50)
printer.print_line("Taller\nline\nspacing")
printer.set_line_height() # Reset to default
printer.justify('L')

# Barcode examples
printer.feed(1)
# CODE39 is the most common alphanumeric barcode
printer.print_barcode("ADAFRUT", printer.CODE39)
printer.set_barcode_height(100)
# Print UPC line on product barcodes
printer.print_barcode("123456789123", printer.UPC_A)

# Print the 75x75 pixel logo in adalogo.py
import gfx.adalogo as adalogo
printer.print_bitmap(adalogo.width, adalogo.height, adalogo.data)

# Print the 135x135 pixel QR code in adaqrcode.py
import gfx.adaqrcode as adaqrcode
printer.print_bitmap(adaqrcode.width, adaqrcode.height, adaqrcode.data)
printer.print_line("Adafruit!")
printer.feed(1)

printer.sleep()      # Tell printer to sleep
printer.wake()       # Call wake() before printing again, even if reset
printer.set_default() # Restore printer to defaults
