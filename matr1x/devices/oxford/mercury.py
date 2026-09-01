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
"""Module with device drivers for Oxford Mercury devices."""

import copy
import logging
import math
import re
from typing import ClassVar, TypeAlias, cast

from wrapt import synchronized

from matr1x.core.visadevice import VisaDevice

logger = logging.getLogger(__name__)

WorkingValue: TypeAlias = float | bool | int
WorkingDict: TypeAlias = dict[str, tuple[list[WorkingValue], str, str, bool]]
QueryDict: TypeAlias = dict[str, str | int]


class MercurySingleAxisIPS(VisaDevice):
    """
    Driver for Mercury-IPS.

    dataDict contains the commands (keys) and also the response from the IPS
    (values).

    Mode of operation:
        1. Querry dicts you want to read - results are written to dictionarys
        2. Results can now be read with the given functions

    Dicts for functions:
        confDictX/Y/Z for magnetic field status (to Setpoint etc.)
        dataDictX/Y/Z for magnetic field functions
        confDictLevel for Helium Fast/Slow
        dataDictLevel for Helium/Nitrogen Levels

    Usually all relevant parameters for operation
    can be found in the workingDict.
    """

    _ID_IPS_TEMPLATE: ClassVar[QueryDict] = {"*IDN?": ""}
    addressSys = "SYS"
    _SYS_DICT_TEMPLATE: ClassVar[QueryDict] = {
        ":TIME": "",
        ":DATE": "",
        ":MAN:HVER": "",
        ":MAN:FVER": "",
        ":MAN:SERL": "",
        ":USER": "",
        ":FLSH": "",
        ":DISP:DIMA": "",
        ":DISP:DIMT": "",
        ":DISP:BRIG": "",
        ":CAT": "",
    }
    addressX = "DEV:GRPZ:PSU"
    _CONF_DICT_X_TEMPLATE: ClassVar[QueryDict] = {
        ":NICK": "",
        ":BIPL": "",
        ":OCNF": "",
        ":CLIM": "",
        ":ATOB": "",
        ":IND": "",
        ":SWPR": "",
        ":SHTC": "",
        ":VLIM": "",
        ":VTRT": "",
        ":ACTN": "",
    }
    _DATA_DICT_X_TEMPLATE: ClassVar[QueryDict] = {
        ":FLD": 0,
        ":RFLD": 0,
        ":FSET": 0,
        ":RFST": 0,
    }
    addressLevel = "DEV:DB3.L1:LVL"
    _CONF_DICT_LEVEL_TEMPLATE: ClassVar[QueryDict] = {
        ":MAN:HVER": "",
        ":MAN:FVER": "",
        ":MAN:SERL": "",
        ":STAT": "",
        ":HEL:PULS:SLOW": "",
        ":HEL:RES:ZERO": "",
        ":HEL:RES:FULL": "",
        ":HEL:PREP:MAG": "",
        ":HEL:PREP:TIM": "",
        ":HEL:PULS:MAG": "",
        ":HEL:PULS:TIM": "",
        ":HEL:PULS:DEL": "",
        ":NIT:FREQ:ZERO": "",
        ":NIT:FREQ:FULL": "",
        ":NIT:PPS": "",
    }
    _DATA_DICT_LEVEL_TEMPLATE: ClassVar[QueryDict] = {":HEL:LEV": 0, ":NIT:LEV": 0}
    addressDict: ClassVar[dict[str, str]] = {
        "sys": addressSys,
        "z": addressX,
        "level": addressLevel,
    }
    _WORKING_DICT_TEMPLATE: ClassVar[WorkingDict] = {
        "zActn": ([0], ":ACTN", addressX, False),
        "zField": ([0], ":FLD", addressX, True),
        "zRate": ([0], ":RFLD", addressX, True),
        "zFSet": ([0], ":FSET", addressX, True),
        "zRSet": ([0], ":RFST", addressX, True),
        "volt": ([0], ":VOLT", addressX, True),
        "LHe": ([0], ":HEL:LEV", addressLevel, True),
        "LN2": ([0], ":NIT:LEV", addressLevel, True),
        "Slow": ([True], ":HEL:PULS:SLOW", addressLevel, False),
    }

    def __init__(self, interface, maxfield=5, maxrate=0.5):
        """
        Initialize the Mercury single axis IPS device.

        Parameters
        ----------
        interface : str
            VISA resource name
        maxfield : float, optional
            Maximum allowed field, by default 5
        maxrate : float, optional
            Maximum allowed rate, by default 0.5
        """
        self._initialize_state()
        super().__init__(interface, write_termination="\n", read_termination="\n")
        self.maxfield = maxfield
        self.maxrate = maxrate
        # determine status now
        self.queryAllDicts()
        self.logAllDicts()

    def _initialize_state(self) -> None:
        """Create response storage that is private to this device instance."""
        self.idIPS = self._ID_IPS_TEMPLATE.copy()
        self.sysDict = self._SYS_DICT_TEMPLATE.copy()
        self.confDictX = self._CONF_DICT_X_TEMPLATE.copy()
        self.dataDictX = self._DATA_DICT_X_TEMPLATE.copy()
        self.confDictLevel = self._CONF_DICT_LEVEL_TEMPLATE.copy()
        self.dataDictLevel = self._DATA_DICT_LEVEL_TEMPLATE.copy()
        self.workingDict: WorkingDict = copy.deepcopy(self._WORKING_DICT_TEMPLATE)

    # high level commands
    @synchronized
    def query(self, command, address="", signal=False):
        """
        Query a value from the device.

        Parameters
        ----------
        command : str
            Command to send
        address : str, optional
            Device address, by default ""
        signal : bool, optional
            Whether to use the signal variant of the command, by default False

        Returns
        -------
        str
            Response from the device
        """
        if address == "":
            self.write(command)
        else:
            if signal is True:
                self.write("READ:" + address + ":SIG" + command + "?")
            else:
                self.write("READ:" + address + command + "?")
        return self.read()

    @synchronized
    def setVal(self, setpoint, command, address="", signal=False):
        """
        Set a value on the device.

        Parameters
        ----------
        setpoint : float or str
            Value to set
        command : str
            Command to use
        address : str, optional
            Device address, by default ""
        signal : bool, optional
            Whether to use the signal variant of the command, by default False

        Returns
        -------
        str
            Response from the device
        """
        try:
            dummy = f"{float(setpoint):.5f}"
        except ValueError:
            dummy = str(setpoint)
        if signal is True:
            self.write("SET:" + address + ":SIG" + command + ":" + dummy)
        else:
            self.write("SET:" + address + command + ":" + dummy)
        return self.read()

    # utility functions
    @synchronized
    def queryDict(self, queryDict, address="", signal=False):
        """
        Query all entries in a dictionary.

        Parameters
        ----------
        queryDict : dict
            Dictionary containing commands as keys
        address : str, optional
            Device address, by default ""
        signal : bool, optional
            Whether to use the signal variant of the command, by default False
        """
        for key in queryDict:
            queryDict[key] = self.query(key, address, signal)

    @synchronized
    def queryWorkingDict(self):
        """
        Query all entries in the working dictionary.

        Updates the values in the working dictionary with current device
        values.
        """
        status = ["HOLD", "RTOS", "RTOZ", "CLMP"]
        for key in self.workingDict:
            dummy = self.query(*self.workingDict[key][1:]).split(":")[-1].strip("\n")
            try:
                self.workingDict[key][0][0] = float(
                    re.findall(r"([+-]?(?:\d+(?:\.\d*)?)(?:[eE][-+]\d+)?)", dummy)[0]
                )
            except (TypeError, IndexError):
                # If float conversion fails, try bool conversion
                if dummy == "ON":
                    self.workingDict[key][0][0] = True
                elif dummy == "OFF":
                    self.workingDict[key][0][0] = False
                else:
                    # Must be action
                    try:
                        self.workingDict[key][0][0] = status.index(dummy)
                    except ValueError:
                        # what happened?
                        logger.info(
                            "Non bool value at %s is %s and can not be assigned to status",
                            key,
                            dummy,
                        )

    def getDictValue(self, key):
        """
        Get a value from the working dictionary.

        Parameters
        ----------
        key : str
            Key in the working dictionary

        Returns
        -------
        float or bool
            Value from the working dictionary
        """
        return self.workingDict[key][0][0]

    # status functions
    def queryAllDicts(self):
        """Query all dictionaries to update their values."""
        self.queryID()
        self.querySysConf()
        self.queryMagnetConf()
        self.queryLevelMeter()
        self.queryMagnetStatus()
        self.queryLevelMeterStatus()
        self.queryWorkingDict()

    def queryID(self):
        """Query the device ID."""
        self.queryDict(self.idIPS)

    def querySysConf(self):
        """Query the system configuration."""
        self.queryDict(self.sysDict, self.addressSys)

    def queryMagnetConf(self):
        """Query the magnet configuration."""
        self.queryDict(self.confDictX, self.addressX)

    def queryLevelMeter(self):
        """Query the level meter configuration."""
        self.queryDict(self.confDictLevel, self.addressLevel)

    def queryLevelMeterStatus(self):
        """Query the level meter status."""
        self.queryDict(self.dataDictLevel, self.addressLevel, True)

    def queryMagnetStatus(self):
        """Query the magnet status."""
        self.queryDict(self.dataDictX, self.addressX, True)

    def logAllDicts(self):
        """Log the contents of all dictionaries for debugging."""
        logger.debug("IPS-ID: %s", self.idIPS)
        logger.debug("IPS-SYSCONF: %s", self.sysDict)
        logger.debug("IPS-MAGNETCONF Z: %s", self.confDictX)
        logger.debug("IPS-MAGNETSTATUS Z: %s", self.dataDictX)
        logger.debug("ITC-LEVELCONF: %s", self.confDictLevel)
        logger.debug("IPS-LEVELSTATUS: %s", self.dataDictLevel)
        logger.debug("IPS-WORKING DICT: %s", self.workingDict)

    # driver functions
    def setMagneticField(self, xval):
        """
        Set the magnetic field on the x axis.

        Parameters
        ----------
        xval : float
            Target magnetic field value

        Notes
        -----
        Values exceeding the maximum field limits will be clamped.
        """
        if self.maxfield < xval:
            xval = self.maxfield
        elif -self.maxfield > xval:
            xval = -self.maxfield
        self.setVal(xval, *self.workingDict["zFSet"][1:])

    def getMagneticFields(self, setp=False):
        """
        Get the current magnetic field values.

        Parameters
        ----------
        setp : bool, optional
            If True, also return the setpoints, by default False

        Returns
        -------
        tuple
            Current field value(s), and setpoint(s) if requested
        """
        if setp is True:
            return (self.getDictValue("zField"), self.getDictValue("zFSet"))
        else:
            return self.getDictValue("zField")

    def setMagneticFieldRate(self, rate, axis=0):
        """
        Set the rate of change for the magnetic field.

        Parameters
        ----------
        rate : float
            Rate of change in T/min, must be between 0 and maxrate
        axis : int, optional
            Axis to set (0=x), by default 0

        Notes
        -----
        Values outside the allowed range will be clamped.
        """
        if rate < 0:
            rate = 0
        elif self.maxrate < rate:
            rate = self.maxrate
        if axis == 0:
            self.setVal(rate, *self.workingDict["zRSet"][1:])

    def getMagneticFieldRate(self, axis=0, setp=False):
        """
        Get the rate of change for the magnetic field.

        Parameters
        ----------
        axis : int, optional
            Axis to query (0=x, -1=all), by default 0
        setp : bool, optional
            If True, also return the setpoint, by default False

        Returns
        -------
        float or tuple or list
            Current rate value(s), and setpoint(s) if requested
        """
        val = None
        if axis == -1:
            val = [self.getDictValue("zRate")]
            if setp is True:
                val += [self.getDictValue("zRSet")]
        elif axis == 0:
            val = self.getDictValue("zRate")
            if setp is True:
                val = (val, self.getDictValue("zRSet"))
        return val

    def setMagnetStatus(self, state: int | list[int], axis=0):
        """
        Set the status of the magnet.

        Parameters
        ----------
        state : int or list
            Status to set:
            0 - HOLD
            1 - RTOS (Ramp to setpoint)
            2 - RTOZ (Ramp to zero)
            3 - CLMP (Clamped, when current is 0) - disallowed
        axis : int, optional
            Axis to set (-1=take state as list, 0=x), by default 0

        Notes
        -----
        Status 3 (CLMP) is disallowed as it could damage the magnet.
        """
        try:
            if axis != -1:
                state = cast(int, state)
                state = int(state)
                if state > 2:
                    # do NOT set to 3, opens door to breaking magnet!
                    return
                elif state < 0:
                    return
            else:
                state = cast(list[int], state)
                if len(state) != 1:
                    return
                for i in range(1):
                    state[i] = int(state[i])
                    if state[i] > 2:
                        # do NOT set to 3, opens door to breaking magnet!
                        return
                    elif state[i] < 0:
                        return
        except ValueError:
            return
        status = ["HOLD", "RTOS", "RTOZ", "CLMP"]
        if axis == -1:
            state = cast(list[int], state)
            self.setVal(status[state[0]], *self.workingDict["zActn"][1:])
        elif axis == 0:
            state = cast(int, state)
            self.setVal(status[state], *self.workingDict["zActn"][1:])

    def getMagnetStatus(self, axis=0):
        """
        Get the status of the magnet.

        Parameters
        ----------
        axis : int, optional
            Axis to query (-1=all, 0=x), by default 0

        Returns
        -------
        int or list
            Status of the magnet:
            0 - HOLD
            1 - RTOS (Ramp to setpoint)
            2 - RTOZ (Ramp to zero)
            3 - CLMP (Clamped, when current is 0)
        """
        if axis == -1:
            return [self.getDictValue("zActn")]
        elif axis == 0:
            return self.getDictValue("zActn")

    def getVoltage(self):
        """
        Get the current output voltage.

        Returns
        -------
        float
            Current output voltage
        """
        return self.getDictValue("volt")

    def getLevels(self):
        """
        Get the liquid nitrogen and helium levels.

        Returns
        -------
        tuple
            (LN2 level, LHe level)
        """
        return (self.getDictValue("LN2"), self.getDictValue("LHe"))

    def setFastRate(self, slow=True):
        """
        Set the helium level meter to fast or slow mode.

        Parameters
        ----------
        slow : bool, optional
            True for slow mode, False for fast mode, by default True
        """
        if slow is True:
            self.setVal("ON", *self.workingDict["Slow"][1:])
        elif slow is False:
            self.setVal("OFF", *self.workingDict["Slow"][1:])

    def getFastRate(self):
        """
        Get the helium level meter mode.

        Returns
        -------
        bool
            True if in slow mode, False if in fast mode
        """
        return self.getDictValue("Slow")


class MercuryIPS(VisaDevice):
    """
    Driver for multi-axis Mercury IPS.

    dataDict contains the commands (keys) and also the response from the IPS
    (values).

    Mode of operation:
        1. Querry dicts you want to read - results are written to dictionarys
        2. Results can now be read with the given functions

    Dicts for functions:
        confDictX/Y/Z for magnetic field status (to Setpoint etc.)
        dataDictX/Y/Z for magnetic field functions
        confDictLevel for Helium Fast/Slow
        dataDictLevel for Helium/Nitrogen Levels

    Usually all relevant parameters for operation
    can be found in the workingDict.
    """

    _ID_IPS_TEMPLATE: ClassVar[QueryDict] = {"*IDN?": ""}
    addressSys = "SYS"
    _SYS_DICT_TEMPLATE: ClassVar[QueryDict] = {
        ":TIME": "",
        ":DATE": "",
        ":MAN:HVER": "",
        ":MAN:FVER": "",
        ":MAN:SERL": "",
        ":USER": "",
        ":FLSH": "",
        ":DISP:DIMA": "",
        ":DISP:DIMT": "",
        ":DISP:BRIG": "",
        ":CAT": "",
    }
    addressX = "DEV:GRPX:PSU"
    _CONF_DICT_X_TEMPLATE: ClassVar[QueryDict] = {
        ":NICK": "",
        ":BIPL": "",
        ":OCNF": "",
        ":CLIM": "",
        ":ATOB": "",
        ":IND": "",
        ":SWPR": "",
        ":SHTC": "",
        ":VLIM": "",
        ":VTRT": "",
        ":ACTN": "",
    }
    _DATA_DICT_X_TEMPLATE: ClassVar[QueryDict] = {
        ":FLD": 0,
        ":RFLD": 0,
        ":FSET": 0,
        ":RFST": 0,
    }
    addressY = "DEV:GRPY:PSU"
    _CONF_DICT_Y_TEMPLATE: ClassVar[QueryDict] = {
        ":NICK": "",
        ":BIPL": "",
        ":OCNF": "",
        ":CLIM": "",
        ":ATOB": "",
        ":IND": "",
        ":SWPR": "",
        ":SHTC": "",
        ":VLIM": "",
        ":VTRT": "",
        ":ACTN": "",
    }
    _DATA_DICT_Y_TEMPLATE: ClassVar[QueryDict] = {
        ":FLD": 0,
        ":RFLD": 0,
        ":FSET": 0,
        ":RFST": 0,
    }
    addressZ = "DEV:GRPZ:PSU"
    _CONF_DICT_Z_TEMPLATE: ClassVar[QueryDict] = {
        ":NICK": "",
        ":BIPL": "",
        ":OCNF": "",
        ":CLIM": "",
        ":ATOB": "",
        ":IND": "",
        ":SWPR": "",
        ":SHTC": "",
        ":VLIM": "",
        ":VTRT": "",
        ":ACTN": "",
    }
    _DATA_DICT_Z_TEMPLATE: ClassVar[QueryDict] = {
        ":FLD": 0,
        ":RFLD": 0,
        ":FSET": 0,
        ":RFST": 0,
    }
    # requires manual interaction!
    addressLevel = "DEV:DB5.L1:LVL"
    _CONF_DICT_LEVEL_TEMPLATE: ClassVar[QueryDict] = {
        ":MAN:HVER": "",
        ":MAN:FVER": "",
        ":MAN:SERL": "",
        ":STAT": "",
        ":HEL:PULS:SLOW": "",
        ":HEL:RES:ZERO": "",
        ":HEL:RES:FULL": "",
        ":HEL:PREP:MAG": "",
        ":HEL:PREP:TIM": "",
        ":HEL:PULS:MAG": "",
        ":HEL:PULS:TIM": "",
        ":HEL:PULS:DEL": "",
        ":NIT:FREQ:ZERO": "",
        ":NIT:FREQ:FULL": "",
        ":NIT:PPS": "",
    }
    _DATA_DICT_LEVEL_TEMPLATE: ClassVar[QueryDict] = {":HEL:LEV": 0, ":NIT:LEV": 0}
    addressDict: ClassVar[dict[str, str]] = {
        "sys": addressSys,
        "level": addressLevel,
        "x": addressX,
        "y": addressY,
        "z": addressZ,
    }
    _WORKING_DICT_TEMPLATE: ClassVar[WorkingDict] = {
        "LHe": ([0], ":HEL:LEV", addressLevel, True),
        "LN2": ([0], ":NIT:LEV", addressLevel, True),
        "Slow": ([True], ":HEL:PULS:SLOW", addressLevel, False),
        "xActn": ([0], ":ACTN", addressX, False),
        "xField": ([0], ":FLD", addressX, True),
        "xRate": ([0], ":RFLD", addressX, True),
        "xFSet": ([0], ":FSET", addressX, True),
        "xRSet": ([0], ":RFST", addressX, True),
        "yActn": ([0], ":ACTN", addressY, False),
        "yField": ([0], ":FLD", addressY, True),
        "yRate": ([0], ":RFLD", addressY, True),
        "yFSet": ([0], ":FSET", addressY, True),
        "yRSet": ([0], ":RFST", addressY, True),
        "zActn": ([0], ":ACTN", addressZ, False),
        "zField": ([0], ":FLD", addressZ, True),
        "zRate": ([0], ":RFLD", addressZ, True),
        "zFSet": ([0], ":FSET", addressZ, True),
        "zRSet": ([0], ":RFST", addressZ, True),
    }

    def __init__(self, interface, **kwargs):
        """
        Initialize the Mercury multi-axis IPS device.

        Parameters
        ----------
        interface : str
            VISA resource name
        **kwargs : dict
            Additional arguments passed to the parent class
        """
        self._initialize_state()
        super().__init__(interface, write_termination="\n", read_termination="\n", **kwargs)
        # determine status now
        self.queryAllDicts()
        self.logAllDicts()

    def _initialize_state(self) -> None:
        """Create response storage that is private to this device instance."""
        self.idIPS = self._ID_IPS_TEMPLATE.copy()
        self.sysDict = self._SYS_DICT_TEMPLATE.copy()
        self.confDictX = self._CONF_DICT_X_TEMPLATE.copy()
        self.dataDictX = self._DATA_DICT_X_TEMPLATE.copy()
        self.confDictY = self._CONF_DICT_Y_TEMPLATE.copy()
        self.dataDictY = self._DATA_DICT_Y_TEMPLATE.copy()
        self.confDictZ = self._CONF_DICT_Z_TEMPLATE.copy()
        self.dataDictZ = self._DATA_DICT_Z_TEMPLATE.copy()
        self.confDictLevel = self._CONF_DICT_LEVEL_TEMPLATE.copy()
        self.dataDictLevel = self._DATA_DICT_LEVEL_TEMPLATE.copy()
        self.workingDict: WorkingDict = copy.deepcopy(self._WORKING_DICT_TEMPLATE)

    # high level commands
    @synchronized
    def query_merc(self, command, address="", signal=False):
        """
        Query a value from the device.

        Parameters
        ----------
        command : str
            Command to send
        address : str, optional
            Device address, by default ""
        signal : bool, optional
            Whether to use the signal variant of the command, by default False

        Returns
        -------
        str
            Response from the device
        """
        if address == "":
            return self.query(command)
        elif signal is True:
            return self.query("READ:" + address + ":SIG" + command + "?")
        else:
            return self.query("READ:" + address + command + "?")

    @synchronized
    def setVal(self, setpoint, command, address="", signal=False):
        """
        Set a value on the device.

        Parameters
        ----------
        setpoint : float or str
            Value to set
        command : str
            Command to use
        address : str, optional
            Device address, by default ""
        signal : bool, optional
            Whether to use the signal variant of the command, by default False

        Returns
        -------
        str
            Response from the device
        """
        try:
            dummy = f"{float(setpoint):.5f}"
        except ValueError:
            dummy = str(setpoint)
        if signal is True:
            self.write("SET:" + address + ":SIG" + command + ":" + dummy)
        else:
            self.write("SET:" + address + command + ":" + dummy)
        return self.read()

    # utility functions
    def queryDict(self, queryDict, address="", signal=False):
        """
        Query all entries in a dictionary.

        Parameters
        ----------
        queryDict : dict
            Dictionary containing commands as keys
        address : str, optional
            Device address, by default ""
        signal : bool, optional
            Whether to use the signal variant of the command, by default False
        """
        for key in queryDict:
            queryDict[key] = self.query_merc(key, address, signal)

    @synchronized
    def queryWorkingDict(self):
        """
        Query all entries in the working dictionary.

        Updates the values in the working dictionary with current device
        values.
        """
        status = ["HOLD", "RTOS", "RTOZ", "CLMP"]
        for key in self.workingDict:
            dummy = self.query_merc(*self.workingDict[key][1:]).split(":")[-1].strip("\n")
            try:
                self.workingDict[key][0][0] = float(
                    re.findall(r"([+-]?(?:\d+(?:\.\d*)?)(?:[eE][-+]\d+)?)", dummy)[0]
                )
            except (TypeError, IndexError):
                # If float conversion fails, try bool conversion
                if dummy == "ON":
                    self.workingDict[key][0][0] = True
                elif dummy == "OFF":
                    self.workingDict[key][0][0] = False
                else:
                    # Must be action
                    try:
                        self.workingDict[key][0][0] = status.index(dummy)
                    except ValueError:
                        # what happened?
                        logger.info(
                            "Non bool value at %s is %s and can not be assigned to status",
                            key,
                            dummy,
                        )

    def getDictValue(self, key):
        """
        Get a value from the working dictionary.

        Parameters
        ----------
        key : str
            Key in the working dictionary

        Returns
        -------
        float or bool
            Value from the working dictionary
        """
        return self.workingDict[key][0][0]

    def checkFields(self, xval, yval, zval, tolerance=0.0):
        """
        Check field boundaries and return valid field values.

        Parameters
        ----------
        xval : float
            X-axis field value
        yval : float
            Y-axis field value
        zval : float
            Z-axis field value
        tolerance : float, optional
            Tolerance to apply to limits, by default 0.0

        Returns
        -------
        tuple
            (valid, (xval, yval, zval)) where valid is a boolean indicating if the
            original values were within limits, and the tuple contains the adjusted values
        """
        valid = True
        # check -2 <= xval <= 2
        if 2 + tolerance < abs(xval):
            valid = False
            xval = math.copysign(2, xval)
        # check -2 <= yval <= 2
        if 2 + tolerance < abs(yval):
            valid = False
            yval = math.copysign(2, yval)
        # check -6 <= zval <= 6
        if 6 + tolerance < zval:
            valid = False
            zval = math.copysign(6, yval)
        # check if "ip" field is greater than 1.5T and limit magnitude to 2T
        if 1.5 + tolerance < math.sqrt(xval**2 + yval**2) and 2.0 + tolerance < math.sqrt(
            xval**2 + yval**2 + zval**2
        ):
            # check if 3D field is greater than 2T and limit all axis
            # conserving the direction (really necessary?)
            valid = False
            factor = 2.0 / math.sqrt(xval**2 + yval**2 + zval**2)
            xval = xval * factor
            yval = yval * factor
            zval = zval * factor
        return valid, (xval, yval, zval)

    # status functions
    def queryAllDicts(self):
        """Query all dictionaries to update their values."""
        self.queryID()
        self.querySysConf()
        self.queryMagnetConf()
        self.queryLevelMeter()
        self.queryMagnetStatus()
        self.queryLevelMeterStatus()
        self.queryWorkingDict()

    def queryID(self):
        """Query the device ID."""
        self.queryDict(self.idIPS)

    def querySysConf(self):
        """Query the system configuration."""
        self.queryDict(self.sysDict, self.addressSys)

    def queryLevelMeter(self):
        """Query the level meter configuration."""
        self.queryDict(self.confDictLevel, self.addressLevel)

    def queryMagnetConf(self):
        """Query the magnet configuration for all axes."""
        self.queryDict(self.confDictX, self.addressX)
        self.queryDict(self.confDictY, self.addressY)
        self.queryDict(self.confDictZ, self.addressZ)

    def queryMagnetStatus(self):
        """Query the magnet status for all axes."""
        self.queryDict(self.dataDictX, self.addressX, True)
        self.queryDict(self.dataDictY, self.addressY, True)
        self.queryDict(self.dataDictZ, self.addressZ, True)

    def queryLevelMeterStatus(self):
        """Query the level meter status."""
        self.queryDict(self.dataDictLevel, self.addressLevel, True)

    def logAllDicts(self):
        """Log the contents of all dictionaries for debugging."""
        logger.debug("IPS-ID: %s", self.idIPS)
        logger.debug("IPS-SYSCONF: %s", self.sysDict)
        logger.debug("IPS-MAGNETCONF X: %s", self.confDictX)
        logger.debug("IPS-MAGNETCONF Y: %s", self.confDictY)
        logger.debug("IPS-MAGNETCONF Z: %s", self.confDictZ)
        logger.debug("ITC-LEVELCONF: %s", self.confDictLevel)
        logger.debug("IPS-MAGNETSTATUS X: %s", self.dataDictX)
        logger.debug("IPS-MAGNETSTATUS Y: %s", self.dataDictY)
        logger.debug("IPS-MAGNETSTATUS Z: %s", self.dataDictZ)
        logger.debug("IPS-LEVELSTATUS: %s", self.dataDictLevel)
        logger.debug("IPS-WORKING DICT: %s", self.workingDict)

    # driver functions
    @synchronized
    def setMagneticFields(self, fields):
        """
        Set the magnetic field on all three axes.

        Parameters
        ----------
        fields : list
            List with three entries containing field values [x, y, z] in Tesla.
            Values exceeding the boundaries will be clamped.
        """
        assert len(fields) == 3
        xval, yval, zval = fields
        valid, (xv, yv, zv) = self.checkFields(xval, yval, zval)
        if valid is False:
            logger.info("Magnetic field exceeding limits was set, reduced amplitude")
        # check that values also do not exceed limits with current fields
        self.setVal(xv, *self.workingDict["xFSet"][1:])
        self.setVal(yv, *self.workingDict["yFSet"][1:])
        self.setVal(zv, *self.workingDict["zFSet"][1:])

    def getMagneticFields(self, setp=False):
        """
        Get the current magnetic field values.

        Parameters
        ----------
        setp : bool, optional
            If True, also return the setpoints, by default False

        Returns
        -------
        tuple
            If setp is False, returns (x_field, y_field, z_field)
            If setp is True, returns (x_field, y_field, z_field, x_setpoint, y_setpoint, z_setpoint)
        """
        if setp is True:
            return (
                self.getDictValue("xField"),
                self.getDictValue("yField"),
                self.getDictValue("zField"),
                self.getDictValue("xFSet"),
                self.getDictValue("yFSet"),
                self.getDictValue("zFSet"),
            )
        else:
            return (
                self.getDictValue("xField"),
                self.getDictValue("yField"),
                self.getDictValue("zField"),
            )

    @synchronized
    def setMagneticFieldRate(self, values):
        """
        Set rates of change for all magnetic field axes.

        Parameters
        ----------
        values : list
            List of 3 floats specifying rates for [x, y, z] axes in T/min.
            Values are clamped to valid ranges:
            - x, y axes: 0 to 0.5 T/min
            - z axis: 0 to 1 T/min
        """
        assert len(values) == 3
        for i, val in enumerate(values):
            if val < 0:
                values[i] = 0
            elif val > 0.5 and i != 2:
                values[i] = 0.5
            elif val > 1 and i == 2:
                values[i] = 1
        self.setVal(values[0], *self.workingDict["xRSet"][1:])
        self.setVal(values[1], *self.workingDict["yRSet"][1:])
        self.setVal(values[2], *self.workingDict["zRSet"][1:])

    def getMagneticFieldRate(self, axis=-1, setp=False):
        """
        Get rates of change for magnetic field axes.

        Parameters
        ----------
        axis : int, optional
            Axis to query: 0=x, 1=y, 2=z, -1=all axes, by default -1
        setp : bool, optional
            If True, also return the setpoints, by default False

        Returns
        -------
        float or tuple or list
            If axis is -1, returns list of rates [x, y, z] (and setpoints if requested)
            If axis is 0, 1, or 2, returns rate for that axis (and setpoint if requested)
        """
        val = None
        if axis == -1:
            val = [
                self.getDictValue("xRate"),
                self.getDictValue("yRate"),
                self.getDictValue("zRate"),
            ]
            if setp is True:
                val += [
                    self.getDictValue("xRSet"),
                    self.getDictValue("yRSet"),
                    self.getDictValue("zRSet"),
                ]
        elif axis == 0:
            val = self.getDictValue("xRate")
            if setp is True:
                val = (val, self.getDictValue("xRSet"))
        elif axis == 1:
            val = self.getDictValue("yRate")
            if setp is True:
                val = (val, self.getDictValue("yRSet"))
        elif axis == 2:
            val = self.getDictValue("zRate")
            if setp is True:
                val = (val, self.getDictValue("zRSet"))
        return val

    @synchronized
    def setMagnetStatus(self, state, axis=-1):
        """
        Set the status of the magnet(s).

        Parameters
        ----------
        state : int or list
            Status to set:
            0 - HOLD
            1 - RTOS (Ramp to setpoint)
            2 - RTOZ (Ramp to zero)
            3 - CLMP (Clamped, when current is 0) - disallowed
            If axis is -1, state should be a list of 3 integers for each axis.
        axis : int, optional
            Axis to set: 0=x, 1=y, 2=z, -1=all axes (using state as list), by default -1

        Notes
        -----
        Status 3 (CLMP) is disallowed as it could damage the magnet.
        """
        try:
            if axis != -1:
                state = int(state)
                if state > 2:
                    # do NOT set to 3, opens door to breaking magnet!
                    return
                elif state < 0:
                    return
            else:
                if len(state) != 3:
                    return
                for i in range(3):
                    state[i] = int(state[i])
                    if state[i] > 2:
                        # do NOT set to 3, opens door to breaking magnet!
                        return
                    elif state[i] < 0:
                        return
        except ValueError:
            return
        status = ["HOLD", "RTOS", "RTOZ", "CLMP"]
        if axis == -1:
            state = cast(list[int], state)
            self.setVal(status[state[0]], *self.workingDict["xActn"][1:])
            self.setVal(status[state[1]], *self.workingDict["yActn"][1:])
            self.setVal(status[state[2]], *self.workingDict["zActn"][1:])
        elif axis == 0:
            self.setVal(status[state], *self.workingDict["xActn"][1:])
        elif axis == 1:
            self.setVal(status[state], *self.workingDict["yActn"][1:])
        elif axis == 2:
            self.setVal(status[state], *self.workingDict["zActn"][1:])

    def getMagnetStatus(self, axis=-1):
        """
        Get the status of the magnet(s).

        Parameters
        ----------
        axis : int, optional
            Axis to query: 0=x, 1=y, 2=z, -1=all axes, by default -1

        Returns
        -------
        int or list
            Status of the magnet(s):
            0 - HOLD
            1 - RTOS (Ramp to setpoint)
            2 - RTOZ (Ramp to zero)
            3 - CLMP (Clamped, when current is 0)
            If axis is -1, returns a list of statuses for all three axes.
        """
        if axis == -1:
            return [
                self.getDictValue("xActn"),
                self.getDictValue("yActn"),
                self.getDictValue("zActn"),
            ]
        elif axis == 0:
            return self.getDictValue("xActn")
        elif axis == 1:
            return self.getDictValue("yActn")
        elif axis == 2:
            return self.getDictValue("zActn")

    def getLevels(self):
        """
        Get the liquid nitrogen and helium levels.

        Returns
        -------
        tuple
            (LN2 level, LHe level) as percentage values
        """
        return (self.getDictValue("LN2"), self.getDictValue("LHe"))

    def setFastRate(self, slow=True):
        """
        Set the helium level meter to fast or slow mode.

        Parameters
        ----------
        slow : bool, optional
            True for slow mode, False for fast mode, by default True
        """
        if slow is True:
            self.setVal("ON", *self.workingDict["Slow"][1:])
        elif slow is False:
            self.setVal("OFF", *self.workingDict["Slow"][1:])

    def getFastRate(self):
        """
        Get the helium level meter mode.

        Returns
        -------
        bool
            True if in slow mode, False if in fast mode
        """
        return self.getDictValue("Slow")


class MercuryITC(VisaDevice):
    """
    Driver for Mercury ITC.

    dataDict contains the commands (keys) and also the response from the
    ITC (values)
    """

    _ID_ITC_TEMPLATE: ClassVar[QueryDict] = {"*IDN?": ""}
    addressSys = "SYS"
    _SYS_DICT_TEMPLATE: ClassVar[QueryDict] = {
        ":TIME": "",
        ":DATE": "",
        ":MAN:HVER": "",
        ":MAN:FVER": "",
        ":MAN:SERL": "",
        ":USER": "",
        ":FLSH": "",
        ":DISP:DIMA": "",
        ":DISP:DIMT": "",
        ":DISP:BRIG": "",
        ":CAT": "",
    }
    # user interaction required
    addressTSens = "DEV:MB1.T1:TEMP"
    _CONF_DICT_TSENS_TEMPLATE: ClassVar[QueryDict] = {
        ":NICK": "",
        ":MAN:HVER": "",
        ":MAN:FVER": "",
        ":MAN:SERL": "",
        ":TYPE": "",
        ":EXCT:TYPE": "",
        ":EXCT:MAG": "",
        ":CAL:OFFS": "",
        ":CAL:SCAL": "",
        ":CAL:FILE": "",
        ":CAL:INT": "",
        ":CAL:HOTL": "",
        ":CAL:COLDL": "",
        ":CSMP": "",
    }
    _DATA_DICT_TSENS_TEMPLATE: ClassVar[QueryDict] = {":TEMP": 0}
    # user interaction required
    addressTSensLoop = "DEV:MB1.T1:TEMP:LOOP"
    _CONF_DICT_TSENS_LOOP_TEMPLATE: ClassVar[QueryDict] = {
        ":HTR:UID": "",
        ":AUX:UID": "",
        ":P": "",
        ":I": "",
        ":D": "",
        ":PIDT": "",
        ":PIDF": "",
        ":THTF": "",
        ":SWFL": "",
        ":SWMD": "",
        ":ENAB": "",
        ":TSET": "",
        ":HSET": "",
        ":FSET": "",
        ":RSET": "",
        ":FAUT": "",
        ":RENA": "",
    }
    # requires manual interaction!
    addressHeater = "DEV:MB0.H1:HTR"
    _CONF_DICT_HEATER_TEMPLATE: ClassVar[QueryDict] = {
        ":MAN:HVER": "",
        ":MAN:FVER": "",
        ":MAN:SERL": "",
        ":NICK": "",
        ":VLIM": "",
        ":STAT": "",
        ":RES": "",
        ":PMAX": "",
    }
    _WORKING_DICT_TEMPLATE: ClassVar[WorkingDict] = {
        "Heater": ([0], ":HSET", addressTSensLoop, False),
        "FSet": ([0], ":FSET", addressTSensLoop, False),
        "AHTR": ([0], ":ENAB", addressTSensLoop, False),
        "APID": ([0], ":PIDT", addressTSensLoop, False),
        "P": ([0], ":P", addressTSensLoop, False),
        "I": ([0], ":I", addressTSensLoop, False),
        "D": ([0], ":D", addressTSensLoop, False),
        "TSet": ([0], ":TSET", addressTSensLoop, False),
        "Temp": ([0], ":TEMP", addressTSens, True),
    }

    def __init__(self, interface, **kwargs):
        self._initialize_state()
        super().__init__(interface, write_termination="\n", read_termination="\n", **kwargs)
        self.queryAllDicts()
        self.logAllDicts()

    def _initialize_state(self) -> None:
        """Create response storage that is private to this device instance."""
        self.idITC = self._ID_ITC_TEMPLATE.copy()
        self.sysDict = self._SYS_DICT_TEMPLATE.copy()
        self.confDictTSens = self._CONF_DICT_TSENS_TEMPLATE.copy()
        self.dataDictTSens = self._DATA_DICT_TSENS_TEMPLATE.copy()
        self.confDictTSensLoop = self._CONF_DICT_TSENS_LOOP_TEMPLATE.copy()
        self.confDictHeater = self._CONF_DICT_HEATER_TEMPLATE.copy()
        self.workingDict: WorkingDict = copy.deepcopy(self._WORKING_DICT_TEMPLATE)

    # high level commands
    def query_merc(self, command, address="", signal=False):
        """
        Query a value from the device.

        Parameters
        ----------
        command : str
            Command to send
        address : str, optional
            Device address, by default ""
        signal : bool, optional
            Whether to use the signal variant of the command, by default False

        Returns
        -------
        str
            Response from the device
        """
        if address == "":
            return self.query(command)
        elif signal is True:
            return self.query("READ:" + address + ":SIG" + command + "?")
        else:
            return self.query("READ:" + address + command + "?")

    @synchronized
    def setVal(self, setpoint, command, address="", signal=False, integer=False):
        """
        Set a value on the device.

        Parameters
        ----------
        setpoint : float or str
            Value to set
        command : str
            Command to use
        address : str, optional
            Device address, by default ""
        signal : bool, optional
            Whether to use the signal variant of the command, by default False
        integer : bool, optional
            Whether to format the setpoint as an integer, by default False

        Returns
        -------
        str
            Response from the device
        """
        try:
            if integer is True:
                dummy = str(int(setpoint))
            else:
                dummy = f"{float(setpoint):.10f}"
        except ValueError:
            dummy = str(setpoint)
        if signal is True:
            self.write("SET:" + address + ":SIG" + command + ":" + dummy)
        else:
            self.write("SET:" + address + command + ":" + dummy)
        return self.read()

    # utility functions
    def extractValueFromDict(self, entry):
        """
        Extract a numeric value from a dictionary entry string.

        Parameters
        ----------
        entry : str
            Dictionary entry string containing a value

        Returns
        -------
        float or None
            Extracted numeric value, or None if conversion fails
        """
        dummy = entry.split(":")[-1]
        dummy = re.findall(r"([+-]?(?:\d+(?:\.\d*)?)(?:[eE][-+]\d+)?)", dummy)[0]
        try:
            return float(dummy)
        except TypeError:
            logger.debug("Type error during conversion of dict value %s", dummy)
            return None

    def queryDict(self, queryDict, address="", signal=False):
        """
        Query all entries in a dictionary.

        Parameters
        ----------
        queryDict : dict
            Dictionary containing commands as keys
        address : str, optional
            Device address, by default ""
        signal : bool, optional
            Whether to use the signal variant of the command, by default False
        """
        for key in queryDict:
            queryDict[key] = self.query_merc(key, address, signal)

    @synchronized
    def queryWorkingDict(self):
        """
        Query all entries in the working dictionary.

        Updates the values in the working dictionary with current device
        values.
        """
        for key in self.workingDict:
            dummy = self.query_merc(*self.workingDict[key][1:]).split(":")[-1].strip("\n")
            try:
                self.workingDict[key][0][0] = float(
                    re.findall(r"([+-]?(?:\d+(?:\.\d*)?)(?:[eE][-+]\d+)?)", dummy)[0]
                )
            except (TypeError, IndexError):
                # If float conversion fails, try bool conversion
                if dummy == "ON":
                    self.workingDict[key][0][0] = True
                elif dummy == "OFF":
                    self.workingDict[key][0][0] = False
                else:
                    # what happened?
                    logger.info("Non bool value at %s is %s", key, dummy)

    def getDictValue(self, key):
        """
        Get a value from the working dictionary.

        Parameters
        ----------
        key : str
            Key in the working dictionary

        Returns
        -------
        float or bool
            Value from the working dictionary
        """
        return self.workingDict[key][0][0]

    # status functions
    def queryAllDicts(self):
        """Query all dictionaries to update their values."""
        self.queryID()
        self.querySysConf()
        self.queryTSensConf()
        self.queryTSensLoopConf()
        self.queryHeaterConf()
        self.queryTSensStatus()
        self.queryWorkingDict()

    def queryID(self):
        """Query the device ID."""
        self.queryDict(self.idITC)

    def querySysConf(self):
        """Query the system configuration."""
        self.queryDict(self.sysDict, self.addressSys)

    def queryHeaterConf(self):
        """Query the heater configuration."""
        self.queryDict(self.confDictHeater, self.addressHeater)

    def queryTSensLoopConf(self):
        """Query the temperature sensor loop configuration."""
        self.queryDict(self.confDictTSensLoop, self.addressTSensLoop)

    def queryTSensConf(self):
        """Query the temperature sensor configuration."""
        self.queryDict(self.confDictTSens, self.addressTSens)

    def queryTSensStatus(self):
        """Query the temperature sensor status."""
        self.queryDict(self.dataDictTSens, self.addressTSens, True)

    def logAllDicts(self):
        """Log the contents of all dictionaries for debugging."""
        logger.debug("ITC-ID: %s", self.idITC)
        logger.debug("ITC-SYSCONF: %s", self.sysDict)
        logger.debug("ITC-HEATERCONF: %s", self.confDictHeater)
        logger.debug("ITC-TSENSCONF: %s", self.confDictTSens)
        logger.debug("ITC-TSENSLOOPCONF: %s", self.confDictTSensLoop)
        logger.debug("ITC-TSENSSTATUS: %s", self.dataDictTSens)
        logger.debug("ITC-WORKING DICT: %s", self.workingDict)

    # driver functions
    def setTVTI(self, val):
        """
        Set the temperature setpoint.

        Parameters
        ----------
        val : float
            Temperature setpoint in Kelvin (limited to 0-300K range)
        """
        # Limit TVTI to 300K
        if val < 0:
            val = 0
        elif val > 300:
            val = 300
        self.setVal(val, *self.workingDict["TSet"][1:])

    def getTVTI(self, setp=False):
        """
        Get the current temperature.

        Parameters
        ----------
        setp : bool, optional
            If True, also return the setpoint, by default False

        Returns
        -------
        float or tuple
            Current temperature in Kelvin, or (current_temp, setpoint) if setp=True
        """
        val = self.getDictValue("Temp")
        if setp is True:
            return (val, self.getDictValue("TSet"))
        else:
            return val

    def setNV(self, val):
        """
        Set the needle valve opening.

        Parameters
        ----------
        val : float
            Needle valve opening percentage (0-100%)
        """
        # Limit NV between 0 and 100%
        if val < 0:
            val = 0
        elif val > 100:
            val = 100
        self.setVal(val, *self.workingDict["FSet"][1:])

    def getNV(self):
        """
        Get the needle valve opening.

        Returns
        -------
        float
            Needle valve opening percentage (0-100%)
        """
        return self.getDictValue("FSet")

    def setAutoPID(self, val=True):
        """
        Enable or disable automatic PID control.

        Parameters
        ----------
        val : bool, optional
            True to enable auto PID, False to disable, by default True
        """
        if val is True:
            self.setVal("ON", *self.workingDict["APID"][1:])
        elif val is False:
            self.setVal("OFF", *self.workingDict["APID"][1:])

    def getAutoPID(self):
        """
        Get the automatic PID control state.

        Returns
        -------
        bool
            True if auto PID is enabled, False otherwise
        """
        return self.getDictValue("APID")

    def setAutoHTR(self, val=True):
        """
        Enable or disable automatic heater control.

        Parameters
        ----------
        val : bool, optional
            True to enable auto heater, False to disable, by default True
        """
        if val is True:
            self.setVal("ON", *self.workingDict["AHTR"][1:])
        elif val is False:
            self.setVal("OFF", *self.workingDict["AHTR"][1:])

    def getAutoHTR(self):
        """
        Get the automatic heater control state.

        Returns
        -------
        bool
            True if auto heater is enabled, False otherwise
        """
        return self.getDictValue("AHTR")

    def setPID(self, pid):
        """
        Set PID control parameters.

        Parameters
        ----------
        pid : tuple or list
            Three-element sequence containing (P, I, D) values.
            Negative values will be clamped to 0.
        """
        for parm in pid:
            parm = max(parm, 0)
        self.setVal(pid[0], *self.workingDict["P"][1:])
        self.setVal(pid[1], *self.workingDict["I"][1:])
        self.setVal(pid[2], *self.workingDict["D"][1:])

    def getPID(self):
        """
        Get the current PID control parameters.

        Returns
        -------
        tuple
            (P, I, D) values
        """
        return (self.getDictValue("P"), self.getDictValue("I"), self.getDictValue("D"))

    def setHeater(self, val):
        """
        Set the heater output level.

        Parameters
        ----------
        val : float
            Heater output level (typically 0-100%)
        """
        self.setVal(val, *self.workingDict["Heater"][1:])

    def getHeater(self):
        """
        Get the current heater output level.

        Returns
        -------
        float
            Heater output level (typically 0-100%)
        """
        return self.getDictValue("Heater")
