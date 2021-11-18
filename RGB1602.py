# -*- coding: utf-8 -*-
#!/usr/bin/env python3
########################################################################
# Filename    : RGB1602.py
# Description : Control the WaveShare 1602 RGB LCD
# Author      : WaveShare
# Modification: 14th September 2021
#      Version: V0.1
########################################################################
import time
from smbus import SMBus
b = SMBus(1)

#Device I2C Address
LCD_ADDRESS   =  (0x7c>>1)  #3E
RGB_ADDRESS   =  (0xc0>>1)  #60

# Define some device constants
LCD_DAT = 0x01  # Mode - Sending data
LCD_CMD = 0x00  # Mode - Sending command

# LINE_1 = 0x80   # LCD RAM address for the 1st line
# LINE_2 = 0xC0   # LCD RAM address for the 2nd line
# LINE_3 = 0x94   # LCD RAM address for the 3rd line
# LINE_4 = 0xD4   # LCD RAM address for the 4th line
LCD_LINES = (0x80, 0xC0, 0x94, 0xD4)

#color define

REG_RED    =     0x04
REG_GREEN  =     0x03
REG_BLUE   =     0x02
REG_MODE1  =     0x00
REG_MODE2  =     0x01
REG_OUTPUT =     0x08
LCD_CLEARDISPLAY = 0x01
LCD_RETURNHOME = 0x02
LCD_ENTRYMODESET = 0x04
LCD_DISPLAYCONTROL = 0x08
LCD_CURSORSHIFT = 0x10
LCD_FUNCTIONSET = 0x20
LCD_SETCGRAMADDR = 0x40
LCD_SETDDRAMADDR = 0x80

#flags for display entry mode
LCD_ENTRYRIGHT = 0x00
LCD_ENTRYLEFT = 0x02
LCD_ENTRYSHIFTINCREMENT = 0x01
LCD_ENTRYSHIFTDECREMENT = 0x00

#flags for display on/off control
LCD_DISPLAYON = 0x04
LCD_DISPLAYOFF = 0x00
LCD_CURSORON = 0x02
LCD_CURSOROFF = 0x00
LCD_BLINKON = 0x01
LCD_BLINKOFF = 0x00

#flags for display/cursor shift
LCD_DISPLAYMOVE = 0x08
LCD_CURSORMOVE = 0x00
LCD_MOVERIGHT = 0x04
LCD_MOVELEFT = 0x00

#flags for function set
LCD_8BITMODE = 0x10
LCD_4BITMODE = 0x00
LCD_2LINE = 0x08
LCD_1LINE = 0x00
LCD_5x8DOTS = 0x00


class RGB1602:
  def __init__(self, col, row):
    self._row = row
    self._col = col
    self._backlight = True
    self._last_data = 0x00
    self._showfunction = LCD_4BITMODE | LCD_1LINE | LCD_5x8DOTS;
    self.begin(self._row,self._col)

        
  def command(self,cmd):
    b.write_byte_data(LCD_ADDRESS,0x80,cmd)

  def write(self,data):
    self._last_data = data
    b.write_byte_data(LCD_ADDRESS,0x40,data)
    
  def setReg(self,reg,data):
    b.write_byte_data(RGB_ADDRESS,reg,data)


  def setRGB(self,r,g,b):
    self.setReg(REG_RED,r)
    self.setReg(REG_GREEN,g)
    self.setReg(REG_BLUE,b)

  def setCursor(self,col,row):
    if(row == 0):
      col|=0x80
    else:
      col|=0xc0
    self.command(col)

  def clear(self):
    self.command(LCD_CLEARDISPLAY)
    time.sleep(0.002)

  def printout(self,arg):
    if(isinstance(arg,int)):
      arg=str(arg)

    for x in bytearray(arg,'utf-8'):
      self.write(x)

  def print_line(self, text, line, align='LEFT'):
        """
        Fill a whole line of the LCD with a string

        text:   bytes or str object, str object will be encoded with ASCII
        line:   line number starts from 0
        align:  could be 'LEFT' (default), 'RIGHT' or 'CENTER'
        """

        #if isinstance(text, str):
        #    text = text.encode('ascii')

        text_length = len(text)
        if text_length < self._col:
            blank_space = self._col - text_length
            if align == 'LEFT':
                text = text + ' ' * blank_space
            elif align == 'RIGHT':
                text = ' ' * blank_space + text
            else:
                text = ' ' * (blank_space // 2) + text + ' ' * (blank_space - blank_space // 2)
        else:
            text = text[:self._col]

        #self.write(LCD_LINES[line], LCD_CMD)
        #self.write(LCD_LINES[line])

        self.setCursor(0,line)
        self.printout(text)

  def set_backlight(self, on_off):
    """
    Set whether the LCD backlight is on or off
    """

    if on_off: 
        self.setColorGreen()
    else:
        self.setColorBlack()

  def display(self):
    #self._showcontrol |= LCD_DISPLAYON 
    self.command(LCD_DISPLAYCONTROL | self._showcontrol)

 
  def begin(self,cols,lines):
    if (lines > 1):
        self._showfunction |= LCD_2LINE 
     
    self._numlines = lines 
    self._currline = 0 
     
    time.sleep(0.05)

    
    # Send function set command sequence
    self.command(LCD_FUNCTIONSET | self._showfunction)
    #delayMicroseconds(4500);  # wait more than 4.1ms
    time.sleep(0.005)
    # second try
    self.command(LCD_FUNCTIONSET | self._showfunction);
    #delayMicroseconds(150);
    time.sleep(0.005)
    # third go
    self.command(LCD_FUNCTIONSET | self._showfunction)
    # finally, set # lines, font size, etc.
    self.command(LCD_FUNCTIONSET | self._showfunction)
    # turn the display on with no cursor or blinking default
    self._showcontrol = LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF 
    self.display()
    # clear it off
    self.clear()
    # Initialize to default text direction (for romance languages)
    self._showmode = LCD_ENTRYLEFT | LCD_ENTRYSHIFTDECREMENT 
    # set the entry mode
    self.command(LCD_ENTRYMODESET | self._showmode);

    # backlight init
    self.setReg(REG_MODE1, 0)
    # set LEDs controllable by both PWM and GRPPWM registers
    self.setReg(REG_OUTPUT, 0xFF)
    # set MODE2 values
    # 0010 0000 -> 0x20  (DMBLNK to 1, ie blinky mode)
    self.setReg(REG_MODE2, 0x20)
    

    
    self.setColorWhite()

  def setColorWhite(self):
    self.setRGB(255, 255, 255)

  def setColorRed(self):
    self.setRGB(255, 0, 0)

  def setColorGreen(self):
    self.setRGB(0, 255, 0)

  def setColorBlue(self):
    self.setRGB(0, 0, 255)

  def setColorBlack(self):
    self.setRGB(0, 0, 0)