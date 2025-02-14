# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2006-2025 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import time

import RPi.GPIO as GPIO
import spidev

# There is warning saying to disable warnings is it works anyway
GPIO.setwarnings(False)


class ADS1256():
    """
    Class for handling and setup of the ADS1256 of the Waveshare AD/DA board
    """
    # Definitions of pins used by the SPI
    DRDY = 11
    RST = 12
    SPICS = 15

    # Definitions of the communication parameters
    DRDY_TIMEOUT = 0.5
    DATA_TIMEOUT = 0.00001
    SCLK_FREQUENCY = 7680000
    SPI_FREQUENCY = 500000

    # Register definition
    REG_STATUS = 0
    REG_MUX = 1
    REG_ADCON = 2
    REG_DRATE = 3
    REG_IO = 4
    REG_OFC0 = 5
    REG_OFC1 = 6
    REG_OFC2 = 7
    REG_FSC0 = 8
    REG_FSC1 = 9
    REG_FSC2 = 10

    # Command definition
    CMD_WAKEUP = 0x00  # Completes SYNC and Exits Standby Mode 0000  0000 (00h)
    CMD_RDATA = 0x01  # Read Data 0000  0001 (01h)
    CMD_RDATAC = 0x03  # Read Data Continuously 0000   0011 (03h)
    CMD_SDATAC = 0x0F  # Stop Read Data Continuously 0000   1111 (0Fh)
    CMD_RREG = 0x10  # Read from REG rrr 0001 rrrr (1xh)
    CMD_WREG = 0x50  # Write to REG rrr 0101 rrrr (5xh)
    CMD_SELFCAL = 0xF0  # Offset and Gain Self-Calibration 1111    0000 (F0h)
    CMD_SELFOCAL = 0xF1  # Offset Self-Calibration 1111    0001 (F1h)
    CMD_SELFGCAL = 0xF2  # Gain Self-Calibration 1111    0010 (F2h)
    CMD_SYSOCAL = 0xF3  # System Offset Calibration 1111   0011 (F3h)
    CMD_SYSGCAL = 0xF4  # System Gain Calibration 1111    0100 (F4h)
    CMD_SYNC = 0xFC  # Synchronize the A/D Conversion 1111   1100 (FCh)
    CMD_STANDBY = 0xFD  # Begin Standby Mode 1111   1101 (FDh)
    CMD_RESET = 0xFE  # Reset to Power-Up Values 1111   1110 (FEh)

    # Rate Definition
    ADS1256_30000SPS = 0xFE
    ADS1256_15000SPS = 0xE0
    ADS1256_7500SPS = 0xD0
    ADS1256_3750SPS = 0xC0
    ADS1256_2000SPS = 0xB0
    ADS1256_1000SPS = 0xA1
    ADS1256_500SPS = 0x92
    ADS1256_100SPS = 0x82
    ADS1256_60SPS = 0x72
    ADS1256_50SPS = 0x63
    ADS1256_30SPS = 0x53
    ADS1256_25SPS = 0x43
    ADS1256_15SPS = 0x33
    ADS1256_10SPS = 0x20
    ADS1256_5SPS = 0x13
    ADS1256_2d5SPS = 0x03

    WAIT_WREG = 4e6/SCLK_FREQUENCY
    WAIT_RREG = 4e6/SCLK_FREQUENCY
    WAIT_RDATA = 4e6/SCLK_FREQUENCY
    WAIT_SYNC = 24e6/SCLK_FREQUENCY
    WAIT_RDATAC = 24e6/SCLK_FREQUENCY
    WAIT_DATA = 50e6/SCLK_FREQUENCY
    WAIT_CSLO = 8e6/SCLK_FREQUENCY

    singleEnded = True
    currentChannelPos = 0  # used also for single ended
    currentChannelNeg = 0

    def __init__(self):
        # Initialize the pin layout to BOARD (RPi 40 pin layout)
        GPIO.setmode(GPIO.BOARD)
        # Define SPICS as output and set to HIGH
        GPIO.setup(self.SPICS, GPIO.OUT, initial=GPIO.HIGH)
        # GPIO.setup(self.SPICS, GPIO.IN)
        # Define DRDY as input and switch on pull-up resistor
        GPIO.setup(self.DRDY, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # Define RST as output and set to HIGH
        GPIO.setup(self.RST, GPIO.OUT, initial=GPIO.HIGH)

        self.spi = spidev.SpiDev()
        # open /dev/spidev0,0
        self.spi.open(0, 0)
        # define SPI parameters
        self.spi.bits_per_word = 8
        self.spi.mode = 0b01
        self.spi.max_speed_hz = self.SPI_FREQUENCY
        # read and save ID
        self.ID = self.readChipID()

    # low level functions
    def CS(self, state):
        """
        Sets the chip select to the state given, high/true means chip is NOT
        selected (inverting)
        """
        if state is True:
            self.delayUS(self.WAIT_CSLO)
            GPIO.output(self.SPICS, GPIO.HIGH)
        else:
            GPIO.output(self.SPICS, GPIO.LOW)

    def DRDY_IS_LOW(self):
        """
        Checks the level of DRDY, If low returns True
        """
        return GPIO.input(self.DRDY) == 0

    def reset(self, state):
        """
        Sets the RST pin to state, can be used to reset the ADS1256
        """
        if state is True:
            GPIO.output(self.RST, GPIO.HIGH)
        else:
            GPIO.output(self.RST, GPIO.LOW)

    def delayUS(self, us):
        """
        Delays us microseconds

        Timing is not extremely precise!
        """
        mdelay = us/1000000
        now = time.time()
        until = now+mdelay
        while (until > time.time()):
            pass

    def write(self, cmd):
        """
        Selects the ADS1256 and sends all commands defined in cmds (list!)
        """
        # self.spi.writebytes([cmd])
        self.spi.xfer([cmd], self.SPI_FREQUENCY, 20)

    def read(self, cnt=1):
        """
        reads cnt bits
        """
        # read = self.spi.readbytes(cnt)
        read = self.spi.xfer([0 for i in range(cnt)], self.SPI_FREQUENCY, 20)
        if 1 < cnt:
            return read
        else:
            return read[0]

    def writeRegister(self, register, value, do_cs=True):
        """
        Writes value to register
        """
        if do_cs is True:
            self.CS(False)
        """
        self.write(self.CMD_WREG | register)
        self.write(0x00)
        self.write(value)
        self.delayUS(self.WAIT_WREG)
        """
        self.spi.xfer([self.CMD_WREG | register, 0x00, value])

        if do_cs is True:
            self.CS(True)

    def readRegister(self, register, cnt=0):
        """
        Returns the value of cnt+1 registers
        """
        self.CS(False)
        """
        self.write(self.CMD_RREG | register)
        self.write(cnt & 0x0a)
        self.delayUS(self.WAIT_DATA)
        rep = self.read(cnt+1)
        """
        rep = self.spi.xfer([self.CMD_RREG | register, cnt & 0xf])
        self.delayUS(self.WAIT_DATA)
        rep = self.spi.xfer([0xaa for i in range(cnt+1)])
        self.CS(True)
        if 0 == cnt:
            return rep[0]
        else:
            return rep

    def configADC(self, rate, gain):
        cmds = []
        cmds.append(self.CMD_WREG | 0)
        # Write four consecutive registers
        cmds.append(0x03)
        # Turns the buffer on (buffered ADC inputs)
        # Bit 3 -> 0 - MSB first
        # Bit 2 -> 1 - Auto-Calibration enabled
        # Bit 1 -> 1 - Buffer enabled
        cmds.append((0 << 3) | (1 << 2) | (1 << 1))
        # Unknown, need to check datasheet TODO
        cmds.append(6 << 4 | 7)
        # Defines the gain of the ADC, could be used to increase the
        # precision
        # Turns off Sensor Detect Current Sources and CLKOUT
        cmds.append((0 << 5) | (0 << 3) | (gain << 0))
        # defines the reading rate of the ADC
        cmds.append(rate)
        self.CS(False)
        self.spi.xfer(cmds, self.SPI_FREQUENCY, 20)
        """
        for cmd in cmds:
            self.write(cmd)
        """
        self.CS(True)
        self.waitDRDY()

    def __del__(self):
        self.spi.close()

    # High level functions
    def waitDRDY(self):
        """
        Waits until DRDY is low

        TODO: Implement with a timer and a timeout?
        currently: 0.5/10e-6 steps with 10us delay
        """
        ctime = time.time()
        while ((not self.DRDY_IS_LOW()) and
               time.time() - ctime < self.DRDY_TIMEOUT):
            ctime = time.time()

    def readChipID(self):
        """
        Returns the chip ID
        """
        self.waitDRDY()
        self.CS(False)
        idc = self.readRegister(self.REG_STATUS)
        self.CS(True)
        return idc >> 4

    def _testAD2(self, channel):
        """
        DO NOT USE THIS
        does not work properly but is how the input cycling should be
        implemented for highest throughput, can not get it to work reliably!
        """
        t = time.time()
        self.waitDRDY()
        self.CS(False)
        # select channel
        self.writeRegister(self.REG_MUX,
                           ((4+channel*2) << 4) | (5+channel*2),
                           do_cs=False)
        # arbitrary DRDY
        self.write(self.CMD_SYNC)
        self.delayUS(self.WAIT_SYNC)
        self.write(self.CMD_WAKEUP)
        self.delayUS(2)
        # DRDY SHOULD BE low
        # DRDY SHOULD BE high
        data = self.readData()
        self.CS(True)
        if data & 0x800000:
            data = (data - 0x1000000) + 1
        else:
            data = data & 0xFFFFFF
        return data, 0, 0, 0, 0, time.time()-t

    def testAD(self, channel):
        """
        This is what I found to work... at least 99% of all times
        """
        t = time.time()
        self.CS(False)
        # select channel
        self.writeRegister(self.REG_MUX,
                           ((4+channel*2) << 4) | (5+channel*2),
                           do_cs=False)
        # arbitrary DRDY
        self.write(self.CMD_SYNC)
        self.delayUS(self.WAIT_SYNC)
        self.write(self.CMD_WAKEUP)
        self.delayUS(2)
        # DRDY SHOULD BE low
        self.waitDRDY()
        # DRDY SHOULD BE high
        data = self.readData()
        self.CS(True)
        if data & 0x800000:
            data = (data - 0x1000000) + 1
        else:
            data = data & 0xFFFFFF
        return data, 0, 0, 0, 0, time.time()-t

    def readData(self):
        """
        Reads ADC data from the device and returns the result as unsigned int
        """
        self.write(self.CMD_RDATA)
        self.delayUS(self.WAIT_DATA)
        buf = self.read(3)
        read = (buf[0] << 16) & 0xFF0000
        read |= (buf[1] << 8) & 0x00FF00
        read |= buf[2] & 0x0000FF
        return read

    # Higher level functions
    def readADC(self, channel):
        """
        Sets the channel and returns a current reading

        Parameters:
            channel - can be integer between 0 and 7

        Handles the read as specified in the datasheet
        """
        if channel > 7:
            return
        self.CS(False)
        self.writeRegister(self.REG_MUX,
                           (channel << 4) | 1 << 3,
                           do_cs=False)
        self.write(self.CMD_SYNC)
        self.delayUS(self.WAIT_SYNC)
        self.write(self.CMD_WAKEUP)
        self.delayUS(2)
        # DRDY SHOULD BE low
        self.waitDRDY()
        # DRDY SHOULD BE high
        data = self.readData()
        self.CS(True)
        return data

    def readDiffADC(self, channelPos, channelNeg):
        """
        Sets the differential channels and returns a current reading

        Parameters:
            channelPos - can be integer between 0 and 7
            channelNeg - can be integer between 0 and 7

        Handles the read as specified in the datasheet
        """
        if 7 < channelPos or 7 < channelNeg:
            print("you fail!")
            return
        self.CS(False)
        # select channel
        self.writeRegister(self.REG_MUX,
                           (channelPos << 4) | channelNeg,
                           do_cs=False)
        # arbitrary DRDY
        self.write(self.CMD_SYNC)
        self.delayUS(self.WAIT_SYNC)
        self.write(self.CMD_WAKEUP)
        self.delayUS(2)
        # DRDY SHOULD BE low
        self.waitDRDY()
        # DRDY SHOULD BE high
        data = self.readData()
        self.CS(True)
        return data

    def setGPIODIR(self, direction, pin):
        """
        Set GPIO direction on GPIO pin 0 to 3
        0 is output
        1 is input
        """
        if pin > 3:
            return
        elif pin < 0:
            return
        reg = self.readRegister(self.REG_IO)
        if 1 == direction:
            self.writeRegister(self.REG_IO, (0xff & (reg | (1 << pin+4))))
        elif 0 == direction:
            self.writeRegister(self.REG_IO, (0xff & (reg & ~(1 << pin+4))))

    def setGPIO(self, state, pin):
        """
        Set GPIO pin 0 to 3 from output value to state (0 or 1)
        """
        if pin > 3:
            return
        elif pin < 0:
            return
        reg = self.readRegister(self.REG_IO)
        if bool(state) is True:
            self.writeRegister(self.REG_IO, (0xff & (reg | (1 << pin))))
        elif bool(state) is False:
            self.writeRegister(self.REG_IO, (0xff & (reg & ~(1 << pin))))

    def getGPIO(self, pin):
        """
        Get GPIO pin 0 to 3 from output state (0 or 1)
        """
        if pin > 3:
            return
        elif pin < 0:
            return
        return bool(0xff & (self.readRegister(self.REG_IO) & (1 << pin)))
