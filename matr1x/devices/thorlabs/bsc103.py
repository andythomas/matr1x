# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
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
"""Module provides a class for interfacing with Thorlabs BSC103 motor controllers."""

import logging

from pyvisa import constants

from matr1x.core.visadevice import VisaDevice

logger = logging.getLogger(__name__)


class BSC103(VisaDevice):
    """
    The Thorlabs BSC103 motor controller device class.

    This class could also be used for other devices using the
    APT protocol with little to no change.
    Note that multi channel operation is implemented to a certain degree,
    but not completely and without documentation, as it is not used in
    the BSC103.
    Multi card devices are fully implemented.

    Attributes
    ----------
    debug : int
        The debugging mode.
        If byte 0x01 is set, debug information is written to a
            log file using the logging module.
        If byte 0x02 is set, debug information is written to console.
        0x03 activates both.
    drive_config : dict
        Contains the configuration of the device/motor.
    mb : int
        The address of the motherboard, as specified in the config file.
    drives : list of int
        A list of the addresses of the connected drives.
    ndrives : int
        The number of connected drives.
    uStepsPerStep : int
        The ratio of (internal) micro steps to actual stepper motor steps.
        Specific to the used controller.
    """

    def __init__(self, interface, conf=None, debug=0x00):
        """
        Initialize a new BSC103 device.

        Parameters
        ----------
        interface : str
            The serial port where the device is located.
        conf : dict
            Contains the configuration of the device/motor in question, example
            follows:
                {"name": "Thorlabs DRV001", "mb address": 17,
                "drive addresses": [33, 34, 35], "backlash dist": 0.01,
                "ccw hard limit": 1, "ccw soft limit": 1.0, "cw hard limit": 3,
                "cw soft limit": 3.0, "soft limit mode": 1, "def accn": 1.0,
                "def max vel": 2.0, "def min vel": 0.0, "home dir": 2,
                "home limit switch": 1, "home vel": 1.0, "home zero offset": 3,
                "jog accn": 0.5, "jog max vel": 1.0, "jog min vel": 0.0,
                "jog mode": 2, "jog step size": 0.05, "jog stop mode": 2,
                "power rest" : 20, "power mov" : 100, "pitch": 0.5,
                "steps per rev": 200, "units": 1}
        debug : int, optional
            The debugging mode, by default 0x00
            If byte 0x01 is set, debug information is written to a
                log file using the logging module.
            If byte 0x02 is set, debug information is written to console.
            0x03 activates both.
        """
        if conf is None:
            conf = {}
        self.debug = debug
        super().__init__(
            interface,
            baud_rate=115200,
            timeout=10e3,
            flow_control=constants.VI_ASRL_FLOW_RTS_CTS,
            write_termination="\n",
            read_termination="\n",
        )
        self.drive_config = conf
        # Drive setup:
        # address of motherboard, will fail if conf does not contain these
        self.mb = self.drive_config["mb address"]
        # addresses of connected drives
        self.drives = self.drive_config["drive addresses"]
        # number of drives
        self.ndrives = len(self.drives)
        self.uStepsPerStep = 128

    def printDebug(self, string, color="INFO", warning=False):
        """
        Print a debug string to console or log file.

        The writing location is decided based on the debug attribute of the class.

        Parameters
        ----------
        string : str
            The string containing the debug information.
        color : {'W', 'R', 'WARN', 'INFO'}, optional
            Affects the color of the output printed to console.
            If W or R, it is printed in front of the output.
            Default is 'INFO'.
        warning : bool, optional
            If true, the message is logged as a warning.
            Default is False.
        """
        colors = {
            "W": "\033[94m",
            "R": "\033[92m",
            "WARN": "\033[93m",
            "ENDC": "\033[0m",
            "NONE": "",
        }
        if color == "W":
            string = "W: " + string
        if color == "R":
            string = "R: " + string

        if self.debug & 0x01:
            if warning:
                logger.warning(string)
            else:
                logger.info(string)

        if self.debug & 0x02:
            print(f"{colors.get(color, '')}{string}{colors['ENDC']}")  # noqa: T201

    def bytestostr(self, bytearr):
        """
        Format a bytes type into a string of its hexadecimal representation.

        Parameters
        ----------
        bytearr : bytes
            The bytes to convert to a string.

        Returns
        -------
        str
            Hexadecimal representation of the bytes.
        """
        # helper function to format bytes into
        # string without displaying ascii characters
        return " ".join(format(b, "02X") for b in bytearr)

    def mmto_uSteps(self, mm):
        """
        Convert millimeter to the number of micro steps.

        The conversion happens based on the drive configuration,
        and the value is rounded to the nearest integer.

        Parameters
        ----------
        mm : float
            Distance in millimeters to convert.

        Returns
        -------
        int
            Number of microsteps.
        """
        return int(
            mm
            * (
                self.uStepsPerStep
                * self.drive_config["steps per rev"]
                / self.drive_config["pitch"]
            )
        )

    def uStepsto_mm(self, usteps):
        """
        Convert the number of micro steps to millimeter.

        As specified in the drive configuration.

        Parameters
        ----------
        usteps : int
            The number of micro steps to convert.

        Returns
        -------
        float
            The equivalent distance in millimeters.
        """
        return usteps / (
            self.uStepsPerStep * self.drive_config["steps per rev"] / self.drive_config["pitch"]
        )

    def readPacket(self):
        """
        Read an entire packet from the serial port input buffer.

        Returns
        -------
        BSC103.message
            The read packet.
        """
        assert self._opened
        header = self.read(6)
        packet = (
            self.message.fromBytes(header)
            if header[4] < 128
            else self.message.fromBytes(header + self.read(int.from_bytes(header[2:4], "little")))
        )
        self.printDebug(self.bytestostr(packet.getBytes()), "R")
        return packet

    def id(self):
        """
        Get device identification information.

        Returns
        -------
        str
            Combined model number and notes information.
        """
        assert self._opened
        hwinfo = self.getHWInfo()
        return hwinfo[1] + hwinfo[2]

    def open(self):
        """Open the connection to the device and clear the input buffer."""
        super().open()
        tm = self.connection.timeout
        self.connection.timeout = 100
        self.read_very_eager()
        self.connection.timeout = tm

    def write(self, data):
        """
        Write data to the serial port.

        Parameters
        ----------
        data : bytes or BSC103.message
            The data to be written.
            If data is of type BSC103.message, it is converted into
            a bytes type first.

        Returns
        -------
        int
            The number of written bytes.
        """
        assert self._opened
        bytearr = data.getBytes() if isinstance(data, self.message) else data
        self.printDebug(self.bytestostr(bytearr), "W")
        return super().write(bytearr)

    def ReqResp(self, msg):
        """
        Send a packet to the device, and return the response.

        If the debug option is turned on, check if the length
        of the response matches the expected length,
        as some command have a response length attribute leftover
        from when the read method was used instead of the readPacket method.
        Also check if the response ID is the request ID
        incremented by 1, as this is usually the case
        except for movement commands.
        Display a warning in both cases, this is not totally
        accurate, but sometimes useful.

        Parameters
        ----------
        msg : BSC103.message
            The Request to be written.
            Note that the system will wait for a response,
            so make sure that the request will actually be
            answered by the device
            (Certain commands do not provoke a response).

        Returns
        -------
        BSC103.message
            The received response.
        """
        self.write(msg.getBytes())
        resp = self.readPacket()
        if self.debug:
            if msg.respLen != 0 and msg.respLen != resp.datalen + 6:
                self.printDebug(
                    f"Warning!: {resp.datalen + 6:d} bytes received, "
                    f"{msg.respLen:d} bytes expected",
                    warning=True,
                )
            if msg.msgID + 1 != resp.msgID and resp.msgID != 0x0464:
                self.printDebug(
                    f"Warning!: msgID of response({hex(resp.msgID):s}) does not match "
                    f"msgID of request",
                    color="WARN",
                )
        return resp

    class message:
        """
        The data structure that is used for communication using the APT protocol.

        Messages (packets) consist of a 6 byte header
        (2b message ID, 2b payload, 1b destination address, 1b source address)
        sometimes followed by a variable length data packet.
        If the destination is bitwise OR'd with 0x08,
        a data packet will follow, with the length specified in the
        payload section.
        If not, the payload contains two 1b parameters.
        Little endian convention is normally used for conversion
        between bytes and integers.
        Further information on the message structure can be obtained
        from the APT protocol documentation.

        Attributes
        ----------
        msgID : int
            The message ID, which usually specifies the used command.
        dst : int
            The destination address.
        src : int
            The source address.
        respLen : int
            The expected length of the response, if there is one.
        param1, param2 : int
            The parameters, if the message is header only.
        data : bytes
            The data appended to the message.
        datalen : int
            The length of the data packet.
        longPacket : bool
            True if a data packet follows the header.
        """

        def __init__(self, msgID, payload, dst, src=0x01, respLen=0):
            """
            Construct a message object.

            Parameters
            ----------
            msgID : int
                The message ID, which usually specifies the used command.
            payload : bytes or tuple
                If the payload is of bytes type, a long packet is
                created automatically.
                If not, it should be a tuple of two integers containing
                the parameters.
            dst : int
                The destination address.
            src : int, optional
                The source address, by default 0x01
            respLen : int, optional
                The expected response length.
                If no response is expected, set to 0.
                Default is 0.
            """
            self.msgID = msgID
            self.dst = dst
            self.src = src
            self.respLen = respLen
            self.data = b""

            if isinstance(payload, tuple):
                self.param1 = payload[0]
                self.param2 = payload[1]
                self.longPacket = False
                self.datalen = 0
            else:
                assert isinstance(payload, bytes)
                self.data = payload
                self.datalen = len(payload)
                self.longPacket = True

        def getBytes(self):
            """
            Return the raw bytes of a BSC103.message.

            Returns
            -------
            bytes
                The raw bytes representation of the message.
            """
            if self.longPacket:
                return (
                    self.msgID.to_bytes(2, "little")
                    + self.datalen.to_bytes(2, "little")
                    + (self.dst | 0x80).to_bytes(1, "little")
                    + self.src.to_bytes(1, "little")
                    + self.data
                )
            else:
                return (
                    self.msgID.to_bytes(2, "little")
                    + self.param1.to_bytes(1, "little")
                    + self.param2.to_bytes(1, "little")
                    + self.dst.to_bytes(1, "little")
                    + self.src.to_bytes(1, "little")
                )

        @staticmethod
        def fromBytes(bytearr, respLen=0):
            """
            Create a message object from (read) bytes.

            Parameters
            ----------
            bytearr : bytes
                The bytes to create the message from.
            respLen : int, optional
                The expected response length.
                If no response is expected, set to 0.
                Default is 0.

            Returns
            -------
            BSC103.message
                The created message.
            """
            msgID = int.from_bytes(bytearr[0:2], "little")
            src = bytearr[5]

            if bytearr[4] > 128:
                data = bytearr[6:]
                dst = bytearr[4] - 128
                return BSC103.message(msgID, data, dst, src)
            else:
                param1 = bytearr[2]
                param2 = bytearr[3]
                dst = bytearr[4]
                return BSC103.message(msgID, (param1, param2), dst, src, respLen)

    def initializeComm(self, dst):
        """
        Initialize communication with the controller.

        This message must be sent to the motherboard and all drives as
        part of the initialisation process.

        Parameters
        ----------
        dst : int
            The destination address.
        """
        # Setup message, informs controller of source and destination addresses
        self.write(self.message(0x0018, (0x00, 0x00), dst))

    def getHWInfo(self, dst=0x11):
        """
        Get basic hardware information from a controller.

        Not all information is parsed in this function,
        refer to the documentation.

        Parameters
        ----------
        dst : int, optional
            The destination address, by default 0x11

        Returns
        -------
        tuple
            A tuple containing:
            - SerialNmbr: int - The serial number.
            - ModelNmbr: str - The model number.
            - Notes: str - Information string from the device, usually contains the name.
            - nChannels: int - The number of channels the device can use.
        """
        resp = self.ReqResp(self.message(0x0005, (0x00, 0x00), dst, respLen=90)).data

        # TODO: implement the other values  # noqa: FIX002
        SerialNmbr = int.from_bytes(resp[:4], "little")
        ModelNmbr = resp[4:12].decode("ascii").replace("\x00", "")
        Notes = resp[18:66].decode("ascii").replace("\x00", "")
        nChannels = int.from_bytes(resp[82:84], "little")

        return (SerialNmbr, ModelNmbr, Notes, nChannels)

    def getAxisStatus(self, dst, channel=0x01):
        """
        Get information about the status of a drive.

        The return format is specified in parseMotorStatusPckt.

        Parameters
        ----------
        dst : int
            The destination address.
        channel : int, optional
            The channel number, by default 0x01

        Returns
        -------
        dict
            Motor status information as specified in parseMotorStatusPckt.
        """
        return self.parseMotorStatusPckt(self.ReqResp(self.message(0x0480, (channel, 0x00), dst)))

    def parseMotorStatusPckt(self, packet):
        """
        Extract information from a motor status packet.

        Those packets have an ID of either 0x0481 or 0x0464.
        If the ID does not match, print a warning if debug is enabled.
        This method has not been fully tested yet, so use with caution.

        Parameters
        ----------
        packet : BSC103.message
            The packet to parse.

        Returns
        -------
        dict
            A dictionary containing motor status information:
            - channel: int - Channel number
            - position: float - The current position of the drive in millimeters.
            - encCount: int - Not used on the installed drives, as they have no encoder.
            - switches: str - Hexadecimal representation of the switch status.
                For further information, refer to the APT protocol documentation.
            - ismoving: int - The sign indicates the direction, + is forward.
                1 indicates normal, 2 indicates jogging movement.
                0 means the drive is stationary.
            - motor connected: bool - True if a motor is attached to the drive.
                (not working properly)
            - home status: str - One of {'not homed', 'homeing', 'homed'}
        """
        if packet.msgID == 0x0481 or packet.msgID == 0x0464:
            data = packet.data
            motorStatus = {}

            motorStatus["channel"] = int.from_bytes(data[0:2], "little")
            motorStatus["position"] = self.uStepsto_mm(int.from_bytes(data[2:6], "little"))
            motorStatus["encCount"] = int.from_bytes(data[6:10], "little")

            statusbits = int.from_bytes(data[10:14], "little")
            motorStatus["switches"] = hex(statusbits & 0x0F)
            # 1: moving, 2: jogging; ±: direction
            motorStatus["ismoving"] = {0x10: 1, 0x20: -1, 0x40: 2, 0x80: -2}.get(
                statusbits & 0xF0, 0
            )
            motorStatus["motor connected"] = bool(statusbits & 0x100)
            motorStatus["home status"] = {0x0200: "homing", 0x0400: "homed"}.get(
                statusbits & 0x0F00, "not homed"
            )

            return motorStatus
        else:
            self.printDebug("Can not parse packet, not a status update!", color="WARN")

    def enableAxis(self, dst, channel=0x01, status=True):
        """
        Set the state of an axis to either en- or disabled.

        Parameters
        ----------
        dst : int
            The destination address.
        channel : int, optional
            The channel number, by default 0x01
        status : bool, optional
            If true, enable the axis, else disable it.
            Default is True.
        """
        self.write(self.message(0x0210, (channel, 0x01 if status else 0x02), dst))

    def getHomeParams(self, dst, channel):
        """
        Read the home parameters from a drive.

        Parameters
        ----------
        dst : int
            The destination address.
        channel : int
            The channel number.

        Returns
        -------
        tuple
            A tuple containing:
            - homeDir: bool - True if homing in positive direction, else false.
            - limSwitch: bool - Limit switch settings, see APT protocol documentation for
                more information.
            - homeVel: float - The homing velocity in mm/s.
            - offsetDistance: float - The distance from the limit switch in mm, to where the drive
                moves after homing.
        """
        resp = self.ReqResp(self.message(0x0441, (channel, 0x00), dst, respLen=20)).data

        # True => positive/HW forward, False => negative/HW reverse
        homeDir = int.from_bytes(resp[2:4], "little") != 2
        limSwitch = int.from_bytes(resp[4:6], "little") == 4

        homeVel = self.uStepsto_mm(int.from_bytes(resp[6:10], "little"))
        offsetDist = self.uStepsto_mm(int.from_bytes(resp[10:20], "little"))

        return (homeDir, limSwitch, homeVel, offsetDist)

    def setHomeParams(self, dst, channel, homedir, limSwitch, homeVel, offsetDist):
        """
        Set the home parameters for a drive.

        Parameters
        ----------
        dst : int
            The destination address.
        channel : int
            The channel number.
        homedir : bool
            True if homing in positive direction, else false.
        limSwitch : bool
            Limit switch settings, see APT protocol documentation
                for more information.
        homeVel : float
            The homing velocity in mm/s.
        offsetDist : float
            The distance from the limit switch in mm, to where
            the drive moves after homing.
        """
        data = (
            channel.to_bytes(2, "little")
            + homedir.to_bytes(2, "little")
            + limSwitch.to_bytes(2, "little")
            + int(self.mmto_uSteps(homeVel)).to_bytes(4, "little")
            + int(self.mmto_uSteps(offsetDist)).to_bytes(4, "little")
        )
        self.write(self.message(0x0440, data, dst))

    def getLimSwitchParams(self, dst, channel):
        """
        Read the limit switch settings from a drive.

        See the APT protocol documentation for more information.

        Parameters
        ----------
        dst : int
            The destination address.
        channel : int
            The channel number.

        Returns
        -------
        tuple
            A tuple containing:
            - CWHardLim : int - Clockwise hard limit
            - CCWHardLim : int - Counter-clockwise hard limit
            - CWSoftLim : int - Clockwise soft limit
            - CCWSoftLim : int - Counter-clockwise soft limit
            - SoftLimMode : int - Soft limit mode
        """
        resp = self.ReqResp(self.message(0x0424, (channel, 0x00), dst, respLen=22)).data
        # factor between soft limit values and mm, different from
        # usual value for some reason
        mmtoSoftLimit = 134218

        CWHardLim = int.from_bytes(resp[2:4], "little")
        CCWHardLim = int.from_bytes(resp[4:6], "little")
        CWSoftLim = int.from_bytes(resp[6:10], "little") / mmtoSoftLimit
        CCWSoftLim = int.from_bytes(resp[10:14], "little") / mmtoSoftLimit
        SoftLimMode = int.from_bytes(resp[14:16], "little")
        return (CWHardLim, CCWHardLim, CWSoftLim, CCWSoftLim, SoftLimMode)

    def setLimSwitchParams(
        self, dst, channel, CWHardLim, CCWHardLim, CWSoftLim, CCWSoftLim, SoftLimMode
    ):
        """
        Write the limit switch settings to a drive.

        See the APT protocol documentation for more information.

        Parameters
        ----------
        dst : int
            The destination address.
        channel : int
            The channel number.
        CWHardLim : int
            Clockwise hard limit setting.
        CCWHardLim : int
            Counter-clockwise hard limit setting.
        CWSoftLim : int
            Clockwise soft limit setting.
        CCWSoftLim : int
            Counter-clockwise soft limit setting.
        SoftLimMode : int
            Soft limit mode setting.
        """
        data = (
            channel.to_bytes(2, "little")
            + CWHardLim.to_bytes(2, "little")
            + CCWHardLim.to_bytes(2, "little")
            + CWSoftLim.to_bytes(4, "little")
            + CCWSoftLim.to_bytes(4, "little")
            + SoftLimMode.to_bytes(2, "little")
        )
        self.write(self.message(0x0423, data, dst))

    def getVelParams(self, dst, channel):
        """
        Read the velocity parameters from a drive.

        Parameters
        ----------
        dst : int
            The destination address.
        channel : int
            The channel number.

        Returns
        -------
        tuple
            A tuple containing:
            - minVel : float - The minimum velocity in mm/s, usually zero.
            - acc : float - The acceleration in mm/s².
            - maxVel : float - The maximum velocity in mm/s.
        """
        resp = self.ReqResp(self.message(0x0414, (channel, 0x00), dst, respLen=20)).data
        minVel = self.uStepsto_mm(int.from_bytes(resp[2:6], "little"))
        acc = self.uStepsto_mm(int.from_bytes(resp[6:10], "little"))
        maxVel = self.uStepsto_mm(int.from_bytes(resp[10:14], "little"))
        return (minVel, acc, maxVel)

    def setVelParams(self, dst, channel, minVel, acc, maxVel):
        """
        Set the velocity parameters for a drive.

        Parameters
        ----------
        dst : int
            The destination address.
        channel : int
            The channel number.
        minVel : float
            The minimum velocity in mm/s, usually zero.
        acc : float
            The acceleration in mm/s².
        maxVel : float
            The maximum velocity in mm/s.
        """
        data = (
            channel.to_bytes(2, "little")
            + self.mmto_uSteps(minVel).to_bytes(4, "little")
            + self.mmto_uSteps(acc).to_bytes(4, "little")
            + self.mmto_uSteps(maxVel).to_bytes(4, "little")
        )
        self.write(self.message(0x0413, data, dst))

    def setDriveSettings(self, dst, channel=0x01):
        """
        Set drive according to basic config file settings.

        This includes home, velocity and limit switch settings as well as
        power settings and the backlash correction.
        This method should always be called before attempting to move an axis.

        Parameters
        ----------
        dst : int
            The destination address.
        channel : int, optional
            The channel number, by default 0x01
        """
        self.setVelParams(
            dst,
            channel,
            self.drive_config["def min vel"],
            self.drive_config["def accn"],
            self.drive_config["def max vel"],
        )
        self.setHomeParams(
            dst,
            channel,
            self.drive_config["home dir"],
            self.drive_config["home limit switch"],
            self.drive_config["home vel"],
            self.drive_config["home zero offset"],
        )
        self.setLimSwitchParams(
            dst,
            channel,
            self.drive_config["cw hard limit"],
            self.drive_config["ccw hard limit"],
            int(self.drive_config["cw soft limit"]),
            int(self.drive_config["ccw soft limit"]),
            self.drive_config["soft limit mode"],
        )
        # Backlash dist:
        self.write(
            self.message(
                0x043A,
                channel.to_bytes(2, "little")
                + self.mmto_uSteps(self.drive_config["backlash dist"]).to_bytes(4, "little"),
                dst,
            )
        )
        # Power settings:
        self.write(
            self.message(
                0x0426,
                channel.to_bytes(2, "little")
                + self.drive_config["power rest"].to_bytes(2, "little")
                + self.drive_config["power mov"].to_bytes(2, "little"),
                dst,
            )
        )

    def initDrives(self, axis=None, channel=0x01):
        """
        Initialize communication, set the drive settings and enable multiple drives at once.

        Parameters
        ----------
        axis : list of bool, optional
            List of boolean values, with a length equal to self.ndrives.
            The order of the drives is specified in self.drives.
            If a certain value is set to true, initialize the drive.
            If set to None, all drives get initialized.
            Default is None.
        channel : int, optional
            The channel number, by default 0x01
        """
        # Workaround, sets the default value
        if axis is None:
            axis = [True] * self.ndrives
        assert len(axis) == self.ndrives
        for i in range(self.ndrives):
            if axis[i]:
                self.initializeComm(self.drives[i])
                self.setDriveSettings(self.drives[i], channel=channel)
                self.enableAxis(self.drives[i], channel=channel)

    def home(self, dst, channel=0x01, noResp=False):
        """
        Home a drive.

        Parameters
        ----------
        dst : int
            The destination address.
        channel : int, optional
            The channel number, by default 0x01
        noResp : bool, optional
            If True, do not wait for a response.
            Useful if moving multiple drives at once.
            Default is False.

        Returns
        -------
        str
            Home status:
            - 'homed': if the drive was already homed, or if the
                method waited for a response.
            - 'homing': if the drive is homing, but the method
                did not wait for a response.
            - 'not homed': if something went wrong.
        """
        homestatus = self.getAxisStatus(dst)["home status"]
        if homestatus == "not homed":
            req = self.message(0x0443, (channel, 0x00), dst, respLen=6)
            if not noResp:
                return "homed" if self.ReqResp(req).msgID == 0x0444 else "not homed"
            else:
                self.write(req)
                return "homing"
        elif homestatus == "homing":
            return "homing"
        else:
            return "homed"

    def homeMult(self, axis=None, channel=0x01):
        """
        Home multiple drives at once.

        Parameters
        ----------
        axis : list of bool, optional
            A list of boolean values, with a length equal to self.ndrives.
            The order of the drives is specified in self.drives.
            If a certain value is set to true, home the drive.
            If set to None, all drives get homed.
            Default is None.
        channel : int, optional
            The channel number, by default 0x01

        Returns
        -------
        dict
            A dictionary mapping drive addresses (in hex) to home status strings:
            - 'homed': if the drive was already homed, or if the
                method waited for a response.
            - 'homing': if the drive is homing, but the method
                did not wait for a response.
            - 'not homed': if something went wrong.
        """
        if axis is None:
            axis = [True] * self.ndrives
        assert len(axis) == self.ndrives
        status = {}
        for i in range(self.ndrives):
            if axis[i]:
                status[hex(self.drives[i])] = self.home(self.drives[i], noResp=True)

        for state in status.values():
            if state == "homing":
                resp = self.readPacket()
                status[hex(resp.src)] = "homed" if resp.msgID == 0x0444 else "not homed"
        return status

    def moveRel(self, dst, dist, channel=0x01, noResp=False):
        """
        Move a drive a certain distance relative to the current position.

        Parameters
        ----------
        dst : int
            The destination address.
        dist : float
            The distance in mm which the drive should move by.
        channel : int
             (Default value = 0x01)
        noResp : bool
             (Default value = False)
            If True, do not wait for a response.
            Useful if moving multiple drives at once.

        Returns
        -------
        motorStatusPacket
            Motor status as specified in the parser function.
        """
        req = self.message(
            0x0448,
            channel.to_bytes(2, "little")
            + self.mmto_uSteps(dist).to_bytes(4, "little", signed=True),
            dst,
            respLen=20,
        )
        if not noResp:
            return self.parseMotorStatusPckt(self.ReqResp(req))
        else:
            self.write(req)

    def moveRelMult(self, distArr, channel=0x01):
        """
        Move multiple drive certain distances relative to their current position.

        Parameters
        ----------
        distArr : [float]
            List of the distances in mm, lenght should be equal to self.ndrives.
            Order of the drives is specified in self.drives.
        channel : int
             (Default value = 0x01)

        Returns
        -------
        {
        hex(drive address): motorStatusPacket
            Motor status as specified in the parser function.
        }
        """
        assert len(distArr) == self.ndrives
        status = {}
        for i in range(self.ndrives):
            self.moveRel(self.drives[i], distArr[i], noResp=True)

        for i in range(self.ndrives):
            resp = self.readPacket()
            status[hex(resp.src)] = self.parseMotorStatusPckt(resp)
        return status

    def moveAbs(self, dst, dist, channel=0x01, noResp=False):
        """
        Move a drive to certain position on the axis.

        Parameters
        ----------
        dst : int
            The destination address.
        dist : float
            The position to which the drive should move.
        channel : int
             (Default value = 0x01)
        noResp : bool
             (Default value = False)
            If True, do not wait for a response.
            Useful if moving multiple drives at once.

        Returns
        -------
        motorStatusPacket
            Motor status as specified in the parser function.
        """
        req = self.message(
            0x0453,
            channel.to_bytes(2, "little")
            + self.mmto_uSteps(dist).to_bytes(4, "little", signed=True),
            dst,
            respLen=20,
        )
        if not noResp:
            return self.parseMotorStatusPckt(self.ReqResp(req))
        else:
            self.write(req)

    def moveAbsMult(self, distArr, channel=0x01):
        """
        Move multiple drives to a point of the coordinate system.

        Parameters
        ----------
        distArr : [float]
            List of the coordinates in mm, lenght should be
            equal to self.ndrives.
            Order of the drives is specified in self.drives.
        channel : int
             (Default value = 0x01)

        Returns
        -------
        {
        hex(drive Address): motorStatusPacket
            Motor status as specified in the parser function.
        }
        """
        assert len(distArr) == self.ndrives
        status = {}
        for i in range(self.ndrives):
            self.moveAbs(self.drives[i], distArr[i], noResp=True)

        for i in range(self.ndrives):
            resp = self.readPacket()
            status[hex(resp.src)] = self.parseMotorStatusPckt(resp)
        return status

    def stop(self, dst, channel=0x01, mode=0x02):
        """
        Stop any motion of the drive.

        Not fully tested, so use with caution!

        Parameters
        ----------
        dst : int
            The destination address.
        channel : int
             (Default value = 0x01)
        mode : int
             (Default value = 0x02)
            The stop mode.
            Set to 0x01 to stop immediately, or to 0x02 to stop
            in a controlled (profiled) manner
        """
        self.ReqResp(self.message(0x0465, (channel, mode), dst, respLen=20))
