#!/usr/bin/env python3
########################################################################
# Filename    : FlightStats.py
# Description : Update the LCD Display
# Author      : Jason Brooks www.muckypaws.com
# Modification: 7th August 2021
#      Version: V0.4
########################################################################
#
import json                     # JSON Modules
import math                     # Math Modules
import urllib.request           # URL Request
import signal                   # Trap SIGTERM Events 

from time import sleep          # only need Sleep
from datetime import datetime   # Date Time Module
from pathlib import Path        # Path Module

import RPi.GPIO as GPIO         # GPIO Required
import RGB1602                  # Module Supplied in this Package
import Freenove_DHT as DHT      # Module Supplied in this Package

# Production Flag
PRODUCTION = False

# DEBUG FLAG
DEBUG_FLAG = False

#
# Set Flight Counters
#
FLIGHT_METRICS = {
    "flightCount":  0,
    "flightWithName": 0,
    "flightInvalid": 0,
    "flightSeen": 0,
    "flightSeenPos": 0,
    "flightMax": 0,
    "flightMaxPos": 0,
    "flightMaxAllTime": 0,
    "flightMaxPosAllTime": 0,
    "flightDailyTotal": 0,
    "flightBestDayTotal": 0,
    "flightBestDayDate": "",
    "lowestRoomHumidity": 999,
    "highestRoomHumidity": -1,
    "todaysDate": "2021/08/07",
    "max24": 0,
    "pirSensorLastTrigger": "2021/08/07 00:00:00",
    "lowestRoomTemp": 99.0,
    "highestRoomTemp": -237.15
}

#
# Modify for your environment
#
URL_AIRCRAFT_DATA = "http://flightaware.local:8080/data/aircraft.json"
PATH_INSTALLED_DIRECTORY = "/home/pi/FlightControl/Data/"

#
# If this code is installed on the same device as the FlightAware 
# Software, then you only need call localhost and not resolve the 
# hostname.
#
if PRODUCTION:
    URL_AIRCRAFT_DATA = "http://localhost:8080/data/aircraft.json"

#
# Segregate Development Streams and Data Files from Production
# Good Practice and saves headaches when changing data/file formats
#
if DEBUG_FLAG:
    PATH_INSTALLED_DIRECTORY = "/home/pi/Development/FlightControl/Data/"


PATH_INTERNAL_DATA_FILE = PATH_INSTALLED_DIRECTORY + "internalData.json"
PATH_INTERNAL_STATS_FILE = PATH_INSTALLED_DIRECTORY + "statsData.json"
PATH_INTERNAL_ICAO_FILE = PATH_INSTALLED_DIRECTORY + "ICAOData.json"


# Add Special Squawk Codes You're Interested in Here
# Currently set up for Emergency Codes 7500, 7600 and 7700
#   7500 = HiJack
#   7600 = Radio Failure
#   7700 = Emergency

SPECIAL_SQUAWK_CODES = ["7700", "7600", "7500"]

# Used for determining if internalData needs writing to file.
DIRTY_DATA_FLAG = False

#
#   Define the InfraRed Motion Sensor Pin
#
sensorPin = 23      #GPIO 18 (Not PIN 18) in BCM Mode
ledPin = 24         #GPIO 17 (Not PIN 17) in BCM Mode
HYGRO_PIN = 25
dht = DHT.DHT(HYGRO_PIN)

#
# Toggle for LED BackLight
#
_backLightStatus = True

#
# Maintain a Daily Dictionary of ICAO Flight information 
# Used for counting flights in 24 hour period etc.
#
ICAO_FLIGHT_DICTIONARY = [""]

#
# Using 1602 LCD on i2c Address 0x3F : use i2cdetect -y 1 to validate.
#
# Initialise the LCD Display
#
lcd = RGB1602.RGB1602(16,2)
lcd.clear()
lcd.set_backlight(_backLightStatus)

#
# Get Today's Date
#
def getDateNow():               # get system time
    return datetime.now().strftime('%a %d %b %Y')

#
# Get Today's Time
#
def getTimeNow():               # get system time
    return datetime.now().strftime('%H:%M')

#
# Define the Default Values for the Dictionary (Once Initialisation)
#
def defaultValues():
    global FLIGHT_METRICS
    FLIGHT_METRICS['flightCount'] = 0
    FLIGHT_METRICS['flightWithName'] = 0
    FLIGHT_METRICS['flightSeen'] = 0
    FLIGHT_METRICS['flightSeenPos'] = 0
    FLIGHT_METRICS['flightInvalid'] = 0
    FLIGHT_METRICS['flightMax'] = 0
    FLIGHT_METRICS['flightMaxPos'] = 0
    FLIGHT_METRICS['flightMaxPosAllTime'] = 0
    FLIGHT_METRICS['flightMaxAllTime'] = 0
    FLIGHT_METRICS['flightDailyTotal'] = 0
    FLIGHT_METRICS['max24'] = 0
    FLIGHT_METRICS['lowestRoomTemp'] = 999
    FLIGHT_METRICS['highestRoomTemp'] = -273.15
    FLIGHT_METRICS['todaysDate'] = getDateNow()
    FLIGHT_METRICS['flightBestDayDate'] = getDateNow()
    FLIGHT_METRICS['flightBestDayTotal'] = 0
    FLIGHT_METRICS['pirSensorLastTrigger'] = getDateNow()

    ICAO_FLIGHT_DICTIONARY[0] = getDateNow()

#
# Clear Metrics To be Updated by Parsing the aircraft.json file
#
def clearFlightMetrics():
    global FLIGHT_METRICS
    FLIGHT_METRICS['flightCount']=0
    FLIGHT_METRICS['flightWithName']=0
    FLIGHT_METRICS['flightSeen']=0
    FLIGHT_METRICS['flightSeenPos']=0
    FLIGHT_METRICS['flightInvalid']=0

#
# Clear Metrics To be Updated by Parsing the aircraft.json file
#
def clearFlightMetricsDailyCutover():
    global FLIGHT_METRICS
    global ICAO_FLIGHT_DICTIONARY

    # Clear Flight Metrics
    clearFlightMetrics()

    # Reset Daily Metrics
    FLIGHT_METRICS['flightMax'] = 0
    FLIGHT_METRICS['flightMaxPos'] = 0
    FLIGHT_METRICS['flightDailyTotal'] = 0
    FLIGHT_METRICS['lowestRoomTemp'] = 1000
    FLIGHT_METRICS['highestRoomTemp'] = -273.15
    FLIGHT_METRICS['todaysDate'] = getDateNow()
    FLIGHT_METRICS['flightBestDayTotal'] = 0

    # Empty the total flight Dictionary for 24 hours period.
    ICAO_FLIGHT_DICTIONARY.clear()
    ICAO_FLIGHT_DICTIONARY.append(getDateNow())

#
# Check if Internal Data Available and if so
#   Load it into the dictionary, otherwise, default initialisation
#
def loadData():
    global FLIGHT_METRICS
    global ICAO_FLIGHT_DICTIONARY

    try:
        # initialise default metrics.
        defaultValues()

        # Check if we have an internal data file.
        savedVars = Path(PATH_INTERNAL_DATA_FILE)

        # If a file exists, load the JSON data to the dictionary
        # Also protect against upgrading of the JSON File in the future.
        if savedVars.is_file():
            with open(PATH_INTERNAL_DATA_FILE) as json_file:
                # Load the JSON Data to a Temp Dictionary
                lastKnownData = json.load(json_file)
            if len(lastKnownData) > 0:
                # Copy elements to Global Dictionary (Takes Care in part of versioning)
                for element in lastKnownData:
                    FLIGHT_METRICS[element] = lastKnownData[element]


        # Load the ICAO Data (if available), Discard if not today's feed

        # Delete All Data
        
        savedICAO = Path(PATH_INTERNAL_ICAO_FILE)
        # If a file exists, load the ICAO Dictionary
        if savedICAO.is_file():
            with open(PATH_INTERNAL_ICAO_FILE) as json_file:
                # Load the JSON Data to a Temp Dictionary
                ICAO_FLIGHT_DICTIONARY = json.load(json_file)
            
            if len(ICAO_FLIGHT_DICTIONARY) > 0:
                if ICAO_FLIGHT_DICTIONARY[0] != getDateNow():
                    ICAO_FLIGHT_DICTIONARY.clear()
                    ICAO_FLIGHT_DICTIONARY.append(getDateNow())

    except ValueError:
        print(f"Invalid JSON File Detected: {json_file.name}")
        print("Continuing with Defaults...")
        ICAO_FLIGHT_DICTIONARY.clear()
        ICAO_FLIGHT_DICTIONARY.append(getDateNow())
    except:
        exit(1)

#
# Helper function, Display Error Message and Quit
#
def quitWithErrorMessage(mess1, mess2):
    lcd.clear()
    lcd.print_line(mess1, line=0)
    lcd.print_line(mess2, line=1)
    exit(1)

#
# Helper function, Display Error Message
#
def reportErrorMessage(mess1, mess2):
    lcd.clear()
    lcd.print_line(mess1, line=0)
    lcd.print_line(mess2, line=1)

#
# Write Internal Dictionary Stats to Local File for Recovery
#
def writeInternalData():
    try:
        # Write Internal Metrics
        with open(PATH_INTERNAL_DATA_FILE,'w') as fp:
            json.dump(FLIGHT_METRICS, fp)
            fp.flush()
            fp.close()

        # Store a Copy of the ICAO file
        with open(PATH_INTERNAL_ICAO_FILE,'w') as fp2:
            json.dump(ICAO_FLIGHT_DICTIONARY, fp2)
            fp2.flush()
            fp2.close()
    except:
        quitWithErrorMessage("Failed to Write","Metrics File")

#
# Check for Day Roll Over and reset Daily Stats
#       Process other cutover rules
#
def checkDailyCutover():
    global FLIGHT_METRICS
    global DIRTY_DATA_FLAG

    currentDate = getDateNow()

    if currentDate != FLIGHT_METRICS['todaysDate']:
        # We have achieved cut over...
        #

        statString = FLIGHT_METRICS['todaysDate'] + ", " + \
        str(FLIGHT_METRICS['flightDailyTotal']) + ", " + \
        str(FLIGHT_METRICS['flightBestDayTotal']) + ", " + \
            FLIGHT_METRICS['flightBestDayDate'] + ", " + \
        str(FLIGHT_METRICS['flightMaxPos']) + ", " + \
        str(FLIGHT_METRICS['flightMax']) + ", " + \
        str(FLIGHT_METRICS['flightMaxPosAllTime']) + ", " + \
        str(FLIGHT_METRICS['flightMaxAllTime']) + ", " + \
        '{:.2f}'.format(FLIGHT_METRICS['lowestRoomTemp']) + ", " + \
        '{:.2f}'.format(FLIGHT_METRICS['highestRoomTemp']) + "\n"

        # Reset Daily Metrics
        clearFlightMetricsDailyCutover()

        # Ensure we write the data
        DIRTY_DATA_FLAG = True

        try:
            dataFile = open(PATH_INTERNAL_STATS_FILE, "a")

            dataFile.write(statString)
            dataFile.flush()
            dataFile.close()

        except OSError:
            quitWithErrorMessage("Failed to write","Data File")




#
# Parse the Flight JSON Data.
#
def parseFlightData():
    global FLIGHT_METRICS
    global SPECIAL_SQUAWK_CODES
    global DIRTY_DATA_FLAG


    SpecialFlights = [""]

    #
    # Check for Daily Cutover
    #
    checkDailyCutover()

    # Open the JSON File from Flight Server
    try:
        data = json.loads(urllib.request.urlopen(URL_AIRCRAFT_DATA).read())
    except:
        reportErrorMessage("Failed to Open","Flight URL...")
        return [""]

    #
    # Reset Variables
    #
    clearFlightMetrics()

    SpecialFlights.clear()

    for i in data['aircraft']:
        FLIGHT_METRICS['flightCount']+=1
        data=json.dumps(i, sort_keys=True)
        parsed=json.loads(data)
        if 'seen' in data:
            numSec=parsed['seen']
            if numSec < 60:
                FLIGHT_METRICS['flightSeen'] += 1
            if 'hex' in data:
                if not parsed['hex'] in ICAO_FLIGHT_DICTIONARY:
                    ICAO_FLIGHT_DICTIONARY.append(parsed['hex'].strip())
        if 'seen_pos' in data:
            numSec=parsed['seen_pos']
            if numSec < 60:
                FLIGHT_METRICS['flightSeenPos'] += 1
        if 'flight' in data:
            FLIGHT_METRICS['flightWithName'] += 1
        else:
            FLIGHT_METRICS['flightInvalid'] += 1

        # Check for Special Squawk Codes to Flag
        if 'squawk' in data:
            for emergency in SPECIAL_SQUAWK_CODES:
                if parsed['squawk'] == emergency:
                    if 'flight' in data:
                        SpecialFlights.append(emergency.strip() + ": " + parsed['flight'].strip())
                    else:
                        SpecialFlights.append(emergency.strip() + ": " + parsed['hex'].strip())

    if FLIGHT_METRICS['flightMaxPos'] < FLIGHT_METRICS['flightSeenPos']:
        FLIGHT_METRICS['flightMaxPos'] = FLIGHT_METRICS['flightSeenPos']
        DIRTY_DATA_FLAG = True

    if FLIGHT_METRICS['flightMax'] < FLIGHT_METRICS['flightSeen']:
        FLIGHT_METRICS['flightMax'] = FLIGHT_METRICS['flightSeen']
        DIRTY_DATA_FLAG = True

    # Maximum Daily Flight Metrics Stats
    if FLIGHT_METRICS['flightMax'] > FLIGHT_METRICS['flightMaxAllTime']:
        FLIGHT_METRICS['flightMaxAllTime'] = FLIGHT_METRICS['flightMax']
        DIRTY_DATA_FLAG = True

    if FLIGHT_METRICS['flightMaxPos'] >  FLIGHT_METRICS['flightMaxPosAllTime']:
        FLIGHT_METRICS['flightMaxPosAllTime'] = FLIGHT_METRICS['flightMaxPos']
        DIRTY_DATA_FLAG = True

    FLIGHT_METRICS['flightDailyTotal'] = len(ICAO_FLIGHT_DICTIONARY)

    if FLIGHT_METRICS['flightBestDayTotal'] < FLIGHT_METRICS['flightDailyTotal']:
        FLIGHT_METRICS['flightBestDayTotal'] = FLIGHT_METRICS['flightDailyTotal']
        FLIGHT_METRICS['flightBestDayDate'] = getDateNow()

    return SpecialFlights

#
# When Exiting the program, Ensure we cleanup the LCD Display.
#
def destroy():
    lcd.clear()
    lcd.set_backlight(False)
    GPIO.cleanup()


#
# Set the PIR as a CallBack Function (Non-Blocking)
#
def PIR_Callback(channel):
    global FLIGHT_METRICS
    global _backLightStatus
    global DIRTY_DATA_FLAG

    if DEBUG_FLAG:
        print("Channel: " + str(channel) + " - " , GPIO.input(channel))

    if GPIO.input(channel) == GPIO.HIGH:
        GPIO.output(ledPin, GPIO.HIGH)
        lcd.set_backlight(True)
        FLIGHT_METRICS['pirSensorLastTrigger'] = getDateNow() + ' ' + getTimeNow()
        _backLightStatus = True
        DIRTY_DATA_FLAG = True
    else:
        # Switch the LCD Display off and preserve power
        GPIO.output(ledPin, GPIO.LOW)
        lcd.set_backlight(False)
        lcd.clear()
        _backLightStatus = False

#
# Get the current CPU Temperature
#
def get_cpu_temp():     # get CPU temperature from file "/sys/class/thermal/thermal_zone0/temp"
    tmp = open('/sys/class/thermal/thermal_zone0/temp')
    cpu = tmp.read()
    tmp.close()
    return '{:.2f}'.format(float(cpu)/1000) + '\'C'


#
# Get the current Room Temperature
#
def get_room_temp():
    global FLIGHT_METRICS
    global DIRTY_DATA_FLAG
    global dht
    roomTemp="Probe Error!"
    tempC = -273.15

    chk = dht.readDHT11()	

    if DEBUG_FLAG:
        print("chk : %d, \t Humidity : %.2f, \t Temperature : %.2f "%(chk,dht.humidity,dht.temperature))

    roomTemp = '{:.2f}'.format(dht.temperature) + '\'C'
    roomHumidity = '{:.0f}%'.format(dht.humidity)

    # If Successfully Read Sensor
    if chk == 0:
        if FLIGHT_METRICS['lowestRoomTemp'] > dht.temperature:
            FLIGHT_METRICS['lowestRoomTemp'] = dht.temperature
            DIRTY_DATA_FLAG = True

        if FLIGHT_METRICS['highestRoomTemp'] < dht.temperature:
            FLIGHT_METRICS['highestRoomTemp'] = dht.temperature
            DIRTY_DATA_FLAG = True

        if FLIGHT_METRICS['lowestRoomHumidity'] > dht.humidity:
            FLIGHT_METRICS['lowestRoomHumidity'] = dht.humidity
            DIRTY_DATA_FLAG = True

        if FLIGHT_METRICS['highestRoomHumidity'] < dht.humidity:
            FLIGHT_METRICS['highestRoomHumidity'] = dht.humidity
            DIRTY_DATA_FLAG = True
  

    return chk, roomTemp, roomHumidity

#
# Initialisation of the program and sensors.
#
def setup():
    global _backLightStatus
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(sensorPin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # , pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(ledPin, GPIO.OUT)
    GPIO.setup(HYGRO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    #GPIO.output(ledPin, GPIO.HIGH)
    GPIO.add_event_detect(sensorPin, GPIO.BOTH, callback=PIR_Callback)

    # One time check to see if PIR Triggered and set state correctly.
    if GPIO.input(sensorPin):
        GPIO.output(ledPin, GPIO.HIGH)
        lcd.set_backlight(True)
        lcd.clear()
        _backLightStatus = True
    else:
        GPIO.output(ledPin, GPIO.LOW)
        lcd.set_backlight(False)
        lcd.setColorBlack()
        lcd.clear()
        _backLightStatus = False
        
    loadData()

#
# Crude but works for now.
#
# Display updates
#

#
# Show Current Data and Time
#
def showCurrentTime():
    lcd.print_line(getDateNow(), line=0, align='CENTER')
    lcd.print_line(getTimeNow(), line=1, align='CENTER')

#
# Show the Daily Flight Count Total
#
def showDailyFlightCount():
    lcd.print_line(getTimeNow(), line=0, align='CENTER')
    lcd.print_line("  Daily: " +str(FLIGHT_METRICS['flightDailyTotal']), line = 1, align='LEFT')

#
# Show Flight Statistics
#
def showCurrentFlightStats():
    lcd.print_line('FLIGHTS: ' + str(FLIGHT_METRICS['flightSeen']), line=0)
    lcd.print_line('    POS: ' + str(FLIGHT_METRICS['flightSeenPos']), line=1)

#
# Show Max Flight Statistics
#
def showCurrentFlightDailyMaxStats():
    lcd.print_line('    MAX: ' + str(FLIGHT_METRICS['flightMax']), line=0)
    lcd.print_line('MAX POS: ' + str(FLIGHT_METRICS['flightMaxPos']), line=1)

#
# Show All Time Max Flight Statistics
#
def showCurrentFlightAllTimeMaxStats():
    lcd.print_line('AT     MAX: ' + str(FLIGHT_METRICS['flightMaxAllTime']), line=0)
    lcd.print_line('AT MAX POS: ' + str(FLIGHT_METRICS['flightMaxPosAllTime']), line=1)


#
# Show CPU Temperature
#
def showRoomStats():
    #lcd.print_line(getDateNow(), line=0, align='CENTER')
    roomTemp = get_room_temp()
    lcd.print_line('    Room: ' + roomTemp[1], line=0, align='CENTER')
    lcd.print_line('Humidity: ' + roomTemp[2], line=1, align='LEFT')

    #lcd.print_line("CPU: " + get_cpu_temp(), line=1, align='CENTER')


def showEmergencyAircraft(aircraft):

    if len(aircraft) > 0:
        lcd.setColorRed()
        lcd.print_line('** Emergency **', line=0, align='CENTER')

        for text in aircraft:
            msg = text.strip() + " "
            lcd.print_line(msg, line=1, align="CENTER")
            sleep(4)

        lcd.setColorBlue()


#
# Signal Handler
#
def sigterm_handler(_signo, _stack_frame):
    handleShutdownGracefully()
    destroy()
    exit(0)

#
# Any shutdown tasks to be added here
#
def handleShutdownGracefully():
    writeInternalData()
    GPIO.cleanup()


#
# Main Program Loop
#
def loop():
    global DIRTY_DATA_FLAG
    counter = 0
    sleepCounter = 0

    if DEBUG_FLAG:
        counter = 11

    while True:
        # Check Room Temperature Stats
        # get_room_temp()

        specialFlights = parseFlightData()
        lcd.setCursor(0, 0)  # set cursor position

        if _backLightStatus:
            if counter == 0:
                showCurrentTime()

            if counter > 0 and counter < 10:
                if (counter % 2) == 1:
                    showCurrentFlightStats()
                else:
                    if len(specialFlights) > 0:
                        showEmergencyAircraft(specialFlights)
                    showDailyFlightCount()

            if counter == 11:
                showRoomStats()

            if counter == 12:
                showCurrentFlightDailyMaxStats()
                

            if counter == 13:
                showCurrentFlightAllTimeMaxStats()

            counter += 1

            if counter > 13:
                counter = 0

        else:
            # Reset Counter so LCD At start of Wake Up
            counter = 0
            sleepCounter += 1
            if sleepCounter > 11:
                get_room_temp()
                sleepCounter = 0


        if DIRTY_DATA_FLAG:
            writeInternalData() # Update Internal File Just in Case.
            DIRTY_DATA_FLAG = False

        sleep(5)    # Force Sleep reduce CPU overhead.

#
# Main Program...
#
if __name__ == '__main__':
    signal.signal(signal.SIGTERM, sigterm_handler)
    setup()

    try:
        loop()

    except KeyboardInterrupt:
        print("Stopped by User")

    finally:
        destroy()
        print("Quitting Gracefully")
        handleShutdownGracefully()


    #writeInternalData()
    #destroy()
