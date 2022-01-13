import logging
import math
import re

from wrapt import synchronized

from .visadevice import VisaDevice

logger = logging.getLogger(__name__)


class MercurySingleAxisIPS(VisaDevice):
    """
    Driver for Mercury-IPS
    dataDict contains the commands (keys) and also the response from the IPS
    (values)
    Mode of operation:
        1. Querry dicts you want to read - results are written to dictionarys
        2. Results can now be read with the given functions
        Dicts for functions:
            confDictX/Y/Z for magnetic field status (to Setpoint etc.)
            dataDictX/Y/Z for magnetic field functions
            confDictLevel for Helium Fast/Slow
            dataDictLevel for Helium/Nitrogen Levels
    Usually all relevant parameters for operation
    can be found in the workingDict
    """
    idIPS = {"*IDN?": ""}
    addressSys = "SYS"
    sysDict = {":TIME": "", ":DATE": "", ":MAN:HVER": "", ":MAN:FVER": "",
               ":MAN:SERL": "", ":USER": "", ":FLSH": "", ":DISP:DIMA": "",
               ":DISP:DIMT": "", ":DISP:BRIG": "", ":CAT": ""}
    addressX = "DEV:GRPZ:PSU"
    confDictX = {":NICK": "", ":BIPL": "", ":OCNF": "", ":CLIM": "",
                 ":ATOB": "", ":IND": "", ":SWPR": "", ":SHTC": "",
                 ":VLIM": "", ":VTRT": "", ":ACTN": ""}
    dataDictX = {":FLD": 0, ":RFLD": 0, ":FSET": 0, ":RFST": 0}
    addressLevel = "DEV:DB3.L1:LVL"
    confDictLevel = {":MAN:HVER": "", ":MAN:FVER": "", ":MAN:SERL": "",
                     ":STAT": "", ":HEL:PULS:SLOW": "",
                     ":HEL:RES:ZERO": "", ":HEL:RES:FULL": "",
                     ":HEL:PREP:MAG": "", ":HEL:PREP:TIM": "",
                     ":HEL:PULS:MAG": "", ":HEL:PULS:TIM": "",
                     ":HEL:PULS:DEL": "", ":NIT:FREQ:ZERO": "",
                     ":NIT:FREQ:FULL": "", ":NIT:PPS": ""}
    dataDictLevel = {":HEL:LEV": 0, ":NIT:LEV": 0}
    addressDict = {"sys": addressSys, "z": addressX, "level": addressLevel}
    workingDict = {"zActn": ([0], ":ACTN", addressX, False),
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
        super().__init__(interface, write_termination="\n",
                         read_termination="\n")
        self.maxfield = maxfield
        self.maxrate = maxrate
        # determine status now
        self.queryAllDicts()
        self.logAllDicts()

    # high level commands
    @synchronized
    def query(self, command, address="", signal=False):
        if "" == address:
            self.write(command)
        else:
            if signal is True:
                self.write("READ:" + address + ":SIG" + command + "?")
            else:
                self.write("READ:" + address + command + "?")
        return self.read()

    @synchronized
    def setVal(self, setpoint, command, address="", signal=False):
        try:
            dummy = "{:.5f}".format(float(setpoint))
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
        for key in queryDict:
            queryDict[key] = self.query(key, address, signal)

    @synchronized
    def queryWorkingDict(self):
        status = ["HOLD", "RTOS", "RTOZ", "CLMP"]
        for key in self.workingDict:
            dummy = self.query(
                *self.workingDict[key][1:]).split(":")[-1].strip("\n")
            try:
                self.workingDict[key][0][0] = float(re.findall(
                    r"([+-]?(?:\d+(?:\.\d*)?)(?:[eE][-+]\d+)?)", dummy)[0])
            except (TypeError, IndexError):
                # If float conversion fails, try bool conversion
                if "ON" == dummy:
                    self.workingDict[key][0][0] = True
                elif "OFF" == dummy:
                    self.workingDict[key][0][0] = False
                else:
                    # Must be action
                    try:
                        self.workingDict[key][0][0] = status.index(dummy)
                    except ValueError:
                        # what happened?
                        logger.info("Non bool value at " + str(key) +
                                    " is " + dummy + " and can not be" +
                                    " assigned to status")

    def getDictValue(self, key):
        return self.workingDict[key][0][0]

    # status functions
    def queryAllDicts(self):
        self.queryID()
        self.querySysConf()
        self.queryMagnetConf()
        self.queryLevelMeter()
        self.queryMagnetStatus()
        self.queryLevelMeterStatus()
        self.queryWorkingDict()

    def queryID(self):
        self.queryDict(self.idIPS)

    def querySysConf(self):
        self.queryDict(self.sysDict, self.addressSys)

    def queryMagnetConf(self):
        self.queryDict(self.confDictX, self.addressX)

    def queryLevelMeter(self):
        self.queryDict(self.confDictLevel, self.addressLevel)

    def queryLevelMeterStatus(self):
        self.queryDict(self.dataDictLevel, self.addressLevel, True)

    def queryMagnetStatus(self):
        self.queryDict(self.dataDictX, self.addressX, True)

    def logAllDicts(self):
        logger.debug("IPS-ID: " + str(self.idIPS))
        logger.debug("IPS-SYSCONF: " + str(self.sysDict))
        logger.debug("IPS-MAGNETCONF Z: " + str(self.confDictX))
        logger.debug("IPS-MAGNETSTATUS Z: " + str(self.dataDictX))
        logger.debug("ITC-LEVELCONF: " + str(self.confDictLevel))
        logger.debug("IPS-LEVELSTATUS: " + str(self.dataDictLevel))
        logger.debug("IPS-WORKING DICT: " + str(self.workingDict))

    # driver functions
    def setMagneticField(self, xval):
        """
        Sets the magnetic field to "xval" on the x axis,
        Arguments:
            xval:float
        Additionally checks, that all values are within the boundaries
        """
        if self.maxfield < xval:
            xval = self.maxfield
        elif -self.maxfield > xval:
            xval = -self.maxfield
        self.setVal(xval, *self.workingDict["zFSet"][1:])

    def getMagneticFields(self, setp=False):
        """
        Returns the values of the magnetic field
        Arguments:
            setp:bool - if setp is true, returns also the setpoints
        """
        if setp is True:
            return (self.getDictValue("zField"),
                    self.getDictValue("zFSet"))
        else:
            return (self.getDictValue("zField"))

    def setMagneticFieldRate(self, rate, axis=0):
        """
        Set rate of magnetic axis "axis" to "rate"
        Arguments:
            rate:float - can be between 0 and 0.5T/min
            axis:integer - 0=x
        """
        if 0 > rate:
            rate = 0
        elif self.maxrate < rate:
            rate = self.maxrate
        if 0 == axis:
            self.setVal(rate, *self.workingDict["zRSet"][1:])

    def getMagneticFieldRate(self, axis=0, setp=False):
        """
        Get rate of the magnetic axis "axis"
        Arguments:
            axis:integer - 0=x
            setp:bool - If setp is true, also returns the setpoint
        """
        if -1 == axis:
            val = [self.getDictValue("zRate")]
            if setp is True:
                val += [self.getDictValue("zRSet")]
        elif 0 == axis:
            val = self.getDictValue("zRate")
            if setp is True:
                val = (val, self.getDictValue("zRSet"))
        return val

    def setMagnetStatus(self, state, axis=0):
        """
        Set state status of the magnet to state, where state can be 0 to 3
        Arguments:
            state:integer - offers the following options:
                0 - HOLD
                1 - RTOS (Ramp to setpoint)
                2 - RTOZ (Ramp to zero)
                3 - CLMP (Clamped, when current is 0) - disallowed
            axis:integer - choose the axis you want to set:
                -1 - takes state as list
                0 - x
                2 - z
        """
        try:
            if -1 != axis:
                state = int(state)
                if 2 < state:
                    # do NOT set to 3, opens door to breaking magnet!
                    return
                elif 0 > state:
                    return
            else:
                if 1 != len(state):
                    return
                for i in range(1):
                    state[i] = int(state[i])
                    if 2 < state[i]:
                        # do NOT set to 3, opens door to breaking magnet!
                        return
                    elif 0 > state[i]:
                        return
        except ValueError:
            return
        status = ["HOLD", "RTOS", "RTOZ", "CLMP"]
        if -1 == axis:
            self.setVal(status[state[0]], *self.workingDict["zActn"][1:])
        elif 0 == axis:
            self.setVal(status[state], *self.workingDict["zActn"][1:])

    def getMagnetStatus(self, axis=0):
        """ Get state status of the magnet
        Arguments:
            axis:integer - choose the axis you want to set:
                -1 - returns all as list
                0 - x
                1 - y
                2 - z
        Returns:
            state of the magnet (0-3):
                0 - HOLD
                1 - RTOS (Ramp to setpoint)
                2 - RTOZ (Ramp to zero)
                3 - CLMP (Clamped, when current is 0)
        """
        if -1 == axis:
            return [self.getDictValue("zActn")]
        elif 0 == axis:
            return self.getDictValue("zActn")

    def getVoltage(self):
        """ Get state current output voltage
        """
        return self.getDictValue("volt")

    def getLevels(self):
        return (self.getDictValue("LN2"), self.getDictValue("LHe"))

    def setFastRate(self, slow=True):
        if slow is True:
            self.setVal("ON", *self.workingDict["Slow"][1:])
        elif slow is False:
            self.setVal("OFF", *self.workingDict["Slow"][1:])

    def getFastRate(self):
        return self.getDictValue("Slow")


class MercuryIPS(VisaDevice):
    """
    Driver for multi-axis Mercury IPS

    dataDict contains the commands (keys) and also the response from the IPS
    (values)

    Mode of operation:
        1. Querry dicts you want to read - results are written to dictionarys
        2. Results can now be read with the given functions

        Dicts for functions:
            confDictX/Y/Z for magnetic field status (to Setpoint etc.)
            dataDictX/Y/Z for magnetic field functions
            confDictLevel for Helium Fast/Slow
            dataDictLevel for Helium/Nitrogen Levels

    Usually all relevant parameters for operation
    can be found in the workingDict
    """
    idIPS = {"*IDN?": ""}
    addressSys = "SYS"
    sysDict = {":TIME": "", ":DATE": "", ":MAN:HVER": "", ":MAN:FVER": "",
               ":MAN:SERL": "", ":USER": "", ":FLSH": "", ":DISP:DIMA": "",
               ":DISP:DIMT": "", ":DISP:BRIG": "", ":CAT": ""}
    addressX = "DEV:GRPX:PSU"
    confDictX = {":NICK": "", ":BIPL": "", ":OCNF": "", ":CLIM": "",
                 ":ATOB": "", ":IND": "", ":SWPR": "", ":SHTC": "",
                 ":VLIM": "", ":VTRT": "", ":ACTN": ""}
    dataDictX = {":FLD": 0, ":RFLD": 0, ":FSET": 0, ":RFST": 0}
    addressY = "DEV:GRPY:PSU"
    confDictY = {":NICK": "", ":BIPL": "", ":OCNF": "", ":CLIM": "",
                 ":ATOB": "", ":IND": "", ":SWPR": "", ":SHTC": "",
                 ":VLIM": "", ":VTRT": "", ":ACTN": ""}
    dataDictY = {":FLD": 0, ":RFLD": 0, ":FSET": 0, ":RFST": 0}
    addressZ = "DEV:GRPZ:PSU"
    confDictZ = {":NICK": "", ":BIPL": "", ":OCNF": "", ":CLIM": "",
                 ":ATOB": "", ":IND": "", ":SWPR": "", ":SHTC": "",
                 ":VLIM": "", ":VTRT": "", ":ACTN": ""}
    dataDictZ = {":FLD": 0, ":RFLD": 0, ":FSET": 0, ":RFST": 0}
    # requires manual interaction!
    addressLevel = "DEV:DB5.L1:LVL"
    confDictLevel = {":MAN:HVER": "", ":MAN:FVER": "", ":MAN:SERL": "",
                     ":STAT": "", ":HEL:PULS:SLOW": "",
                     ":HEL:RES:ZERO": "", ":HEL:RES:FULL": "",
                     ":HEL:PREP:MAG": "", ":HEL:PREP:TIM": "",
                     ":HEL:PULS:MAG": "", ":HEL:PULS:TIM": "",
                     ":HEL:PULS:DEL": "", ":NIT:FREQ:ZERO": "",
                     ":NIT:FREQ:FULL": "", ":NIT:PPS": ""}
    dataDictLevel = {":HEL:LEV": 0, ":NIT:LEV": 0}
    addressDict = {"sys": addressSys, "level": addressLevel, "x": addressX,
                   "y": addressY, "z": addressZ}
    workingDict = {"LHe": ([0], ":HEL:LEV", addressLevel, True),
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
                   "zRSet": ([0], ":RFST", addressZ, True)}

    def __init__(self, interface):
        super().__init__(interface, write_termination="\n",
                         read_termination="\n")
        # determine status now
        self.queryAllDicts()
        self.logAllDicts()

    # high level commands
    @synchronized
    def query_merc(self, command, address="", signal=False):
        if "" == address:
            return self.query(command)
        elif signal is True:
            return self.query("READ:" + address + ":SIG" + command + "?")
        else:
            return self.query("READ:" + address + command + "?")

    @synchronized
    def setVal(self, setpoint, command, address="", signal=False):
        try:
            dummy = "{:.5f}".format(float(setpoint))
        except ValueError:
            dummy = str(setpoint)
        if signal is True:
            self.write("SET:" + address + ":SIG" + command + ":" + dummy)
        else:
            self.write("SET:" + address + command + ":" + dummy)
        return self.read()

    # utility functions
    def queryDict(self, queryDict, address="", signal=False):
        for key in queryDict:
            queryDict[key] = self.query_merc(key, address, signal)

    @synchronized
    def queryWorkingDict(self):
        status = ["HOLD", "RTOS", "RTOZ", "CLMP"]
        for key in self.workingDict:
            dummy = self.query_merc(
                *self.workingDict[key][1:]).split(":")[-1].strip("\n")
            try:
                self.workingDict[key][0][0] = float(re.findall(
                    r"([+-]?(?:\d+(?:\.\d*)?)(?:[eE][-+]\d+)?)", dummy)[0])
            except (TypeError, IndexError):
                # If float conversion fails, try bool conversion
                if "ON" == dummy:
                    self.workingDict[key][0][0] = True
                elif "OFF" == dummy:
                    self.workingDict[key][0][0] = False
                else:
                    # Must be action
                    try:
                        self.workingDict[key][0][0] = status.index(dummy)
                    except ValueError:
                        # what happened?
                        logger.info("Non bool value at " + str(key) +
                                    " is " + dummy + " and can not be" +
                                    " assigned to status")

    def getDictValue(self, key):
        return self.workingDict[key][0][0]

    def checkFields(self, xval, yval, zval, tolerance=0.0):
        """
        function to check field boundaries and return a valid set of
        fields pointing in the same direction
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
        if 1.5 + tolerance < math.sqrt(xval**2 + yval**2):
            # check if 3D field is greater than 2T and limit all axis
            # conserving the direction (really necessary?)
            if 2.0 + tolerance < math.sqrt(xval**2 + yval**2 + zval**2):
                valid = False
                factor = 2.0 / math.sqrt(xval**2 + yval**2 + zval**2)
                xval = xval * factor
                yval = yval * factor
                zval = zval * factor
        return valid, (xval, yval, zval)

    # status functions
    def queryAllDicts(self):
        self.queryID()
        self.querySysConf()
        self.queryMagnetConf()
        self.queryLevelMeter()
        self.queryMagnetStatus()
        self.queryLevelMeterStatus()
        self.queryWorkingDict()

    def queryID(self):
        self.queryDict(self.idIPS)

    def querySysConf(self):
        self.queryDict(self.sysDict, self.addressSys)

    def queryLevelMeter(self):
        self.queryDict(self.confDictLevel, self.addressLevel)

    def queryMagnetConf(self):
        self.queryDict(self.confDictX, self.addressX)
        self.queryDict(self.confDictY, self.addressY)
        self.queryDict(self.confDictZ, self.addressZ)

    def queryMagnetStatus(self):
        self.queryDict(self.dataDictX, self.addressX, True)
        self.queryDict(self.dataDictY, self.addressY, True)
        self.queryDict(self.dataDictZ, self.addressZ, True)

    def queryLevelMeterStatus(self):
        self.queryDict(self.dataDictLevel, self.addressLevel, True)

    def logAllDicts(self):
        logger.debug("IPS-ID: " + str(self.idIPS))
        logger.debug("IPS-SYSCONF: " + str(self.sysDict))
        logger.debug("IPS-MAGNETCONF X: " + str(self.confDictX))
        logger.debug("IPS-MAGNETCONF Y: " + str(self.confDictY))
        logger.debug("IPS-MAGNETCONF Z: " + str(self.confDictZ))
        logger.debug("ITC-LEVELCONF: " + str(self.confDictLevel))
        logger.debug("IPS-MAGNETSTATUS X: " + str(self.dataDictX))
        logger.debug("IPS-MAGNETSTATUS Y: " + str(self.dataDictY))
        logger.debug("IPS-MAGNETSTATUS Z: " + str(self.dataDictZ))
        logger.debug("IPS-LEVELSTATUS: " + str(self.dataDictLevel))
        logger.debug("IPS-WORKING DICT: " + str(self.workingDict))

    # driver functions
    @synchronized
    def setMagneticFields(self, fields):
        """
        Sets the magnetic field to "xval" on the x axis, "yval" on the y axis
        and "zval" on the z axis.

        Arguments:
            fields:list with three entries
            xval:float
            yval:float
            zval:float

        Additionally checks, that all values are within the boundaries
        """
        assert 3 == len(fields)
        xval, yval, zval = fields
        valid, (xv, yv, zv) = self.checkFields(xval, yval, zval)
        if valid is False:
            logger.info("Magnetic field exceeding limits was set, " +
                        "reduced amplitude")
        # check that values also do not exceed limits with current fields
        self.setVal(xv, *self.workingDict["xFSet"][1:])
        self.setVal(yv, *self.workingDict["yFSet"][1:])
        self.setVal(zv, *self.workingDict["zFSet"][1:])

    def getMagneticFields(self, setp=False):
        """
        Returns the values of the magnetic fields

        Arguments:
            setp:bool - if setp is true, returns also the three setpoints
        """
        if setp is True:
            return (self.getDictValue("xField"),
                    self.getDictValue("yField"),
                    self.getDictValue("zField"),
                    self.getDictValue("xFSet"),
                    self.getDictValue("yFSet"),
                    self.getDictValue("zFSet"))
        else:
            return (self.getDictValue("xField"),
                    self.getDictValue("yField"),
                    self.getDictValue("zField"))

    @synchronized
    def setMagneticFieldRate(self, values):
        """
        Set rate of magnetic axis "axis" to "rate"

        Arguments:
            rates:list of 3 positive floats
        """
        assert 3 == len(values)
        for i, val in enumerate(values):
            if 0 > val:
                values[i] = 0
            elif 0.5 < val and i != 2:
                values[i] = 0.5
            elif 1 < val and i == 2:
                values[i] = 1
        self.setVal(values[0], *self.workingDict["xRSet"][1:])
        self.setVal(values[1], *self.workingDict["yRSet"][1:])
        self.setVal(values[2], *self.workingDict["zRSet"][1:])

    def getMagneticFieldRate(self, axis, setp=False):
        """
        Get rate of the magnetic axis "axis"

        Arguments:
            axis:integer - 0=x, 1=y, 2=z
            setp:bool - If setp is true, also returns the setpoint
        """
        if -1 == axis:
            val = [self.getDictValue("xRate"),
                   self.getDictValue("yRate"),
                   self.getDictValue("zRate")]
            if setp is True:
                val += [self.getDictValue("xRSet"),
                        self.getDictValue("yRSet"),
                        self.getDictValue("zRSet")]
        elif 0 == axis:
            val = self.getDictValue("xRate")
            if setp is True:
                val = (val, self.getDictValue("xRSet"))
        elif 1 == axis:
            val = self.getDictValue("yRate")
            if setp is True:
                val = (val, self.getDictValue("yRSet"))
        elif 2 == axis:
            val = self.getDictValue("zRate")
            if setp is True:
                val = (val, self.getDictValue("zRSet"))
        return val

    @synchronized
    def setMagnetStatus(self, state, axis):
        """
        Set state status of the magnet to state, where state can be 0 to 3

        Arguments:
            state:integer - offers the following options:
                0 - HOLD
                1 - RTOS (Ramp to setpoint)
                2 - RTOZ (Ramp to zero)
                3 - CLMP (Clamped, when current is 0) - disallowed
            axis:integer - choose the axis you want to set:
                -1 - takes state as list
                0 - x
                2 - z
        """
        try:
            if -1 != axis:
                state = int(state)
                if 2 < state:
                    # do NOT set to 3, opens door to breaking magnet!
                    return
                elif 0 > state:
                    return
            else:
                if 3 != len(state):
                    return
                for i in range(3):
                    state[i] = int(state[i])
                    if 2 < state[i]:
                        # do NOT set to 3, opens door to breaking magnet!
                        return
                    elif 0 > state[i]:
                        return
        except ValueError:
            return
        status = ["HOLD", "RTOS", "RTOZ", "CLMP"]
        if -1 == axis:
            self.setVal(status[state[0]], *self.workingDict["xActn"][1:])
            self.setVal(status[state[1]], *self.workingDict["yActn"][1:])
            self.setVal(status[state[2]], *self.workingDict["zActn"][1:])
        elif 0 == axis:
            self.setVal(status[state], *self.workingDict["xActn"][1:])
        elif 1 == axis:
            self.setVal(status[state], *self.workingDict["yActn"][1:])
        elif 2 == axis:
            self.setVal(status[state], *self.workingDict["zActn"][1:])

    def getMagnetStatus(self, axis):
        """ Get state status of the magnet

        Arguments:
            axis:integer - choose the axis you want to set:
                -1 - returns all as list
                0 - x
                1 - y
                2 - z

        Returns:
            state of the magnet (0-3):
                0 - HOLD
                1 - RTOS (Ramp to setpoint)
                2 - RTOZ (Ramp to zero)
                3 - CLMP (Clamped, when current is 0)
        """
        if -1 == axis:
            return [self.getDictValue("xActn"),
                    self.getDictValue("yActn"),
                    self.getDictValue("zActn")]
        elif 0 == axis:
            return self.getDictValue("xActn")
        elif 1 == axis:
            return self.getDictValue("yActn")
        elif 2 == axis:
            return self.getDictValue("zActn")

    def getLevels(self):
        return (self.getDictValue("LN2"), self.getDictValue("LHe"))

    def setFastRate(self, slow=True):
        if slow is True:
            self.setVal("ON", *self.workingDict["Slow"][1:])
        elif slow is False:
            self.setVal("OFF", *self.workingDict["Slow"][1:])

    def getFastRate(self):
        return self.getDictValue("Slow")


class MercuryITC(VisaDevice):
    """
    Driver for Mercury ITC

    dataDict contains the commands (keys) and also the response from the ITC
    (values)
    """
    idITC = {"*IDN?": ""}
    addressSys = "SYS"
    sysDict = {":TIME": "", ":DATE": "", ":MAN:HVER": "", ":MAN:FVER": "",
               ":MAN:SERL": "", ":USER": "", ":FLSH": "", ":DISP:DIMA": "",
               ":DISP:DIMT": "", ":DISP:BRIG": "", ":CAT": ""}
    # user interaction required
    addressTSens = "DEV:MB1.T1:TEMP"
    confDictTSens = {":NICK": "", ":MAN:HVER": "", ":MAN:FVER": "",
                     ":MAN:SERL": "",
                     ":TYPE": "", ":EXCT:TYPE": "", ":EXCT:MAG": "",
                     ":CAL:OFFS": "", ":CAL:SCAL": "", ":CAL:FILE": "",
                     ":CAL:INT": "", ":CAL:HOTL": "", ":CAL:COLDL": "",
                     ":CSMP": ""}
    dataDictTSens = {":TEMP": 0}
    # user interaction required
    addressTSensLoop = "DEV:MB1.T1:TEMP:LOOP"
    confDictTSensLoop = {":HTR:UID": "", ":AUX:UID": "", ":P": "", ":I": "",
                         ":D": "", ":PIDT": "", ":PIDF": "", ":THTF": "",
                         ":SWFL": "", ":SWMD": "", ":ENAB": "", ":TSET": "",
                         ":HSET": "", ":FSET": "", ":RSET": "", ":FAUT": "",
                         ":RENA": ""}
    # requires manual interaction!
    addressHeater = "DEV:MB0.H1:HTR"
    confDictHeater = {":MAN:HVER": "", ":MAN:FVER": "", ":MAN:SERL": "",
                      ":NICK": "", ":VLIM": "", ":STAT": "", ":RES": "",
                      ":PMAX": ""}
    workingDict = {"Heater": ([0], ":HSET", addressTSensLoop, False),
                   "FSet": ([0], ":FSET", addressTSensLoop, False),
                   "AHTR": ([0], ":ENAB", addressTSensLoop, False),
                   "APID": ([0], ":PIDT", addressTSensLoop, False),
                   "P": ([0], ":P", addressTSensLoop, False),
                   "I": ([0], ":I", addressTSensLoop, False),
                   "D": ([0], ":D", addressTSensLoop, False),
                   "TSet": ([0], ":TSET", addressTSensLoop, False),
                   "Temp": ([0], ":TEMP", addressTSens, True)}

    def __init__(self, interface):
        super().__init__(interface, write_termination="\n",
                         read_termination="\n")
        self.queryAllDicts()
        self.logAllDicts()

    # high level commands
    def query_merc(self, command, address="", signal=False):
        if "" == address:
            return self.query(command)
        elif signal is True:
            return self.query("READ:" + address + ":SIG" + command + "?")
        else:
            return self.query("READ:" + address + command + "?")

    @synchronized
    def setVal(self, setpoint, command, address="", signal=False,
               integer=False):
        try:
            if integer is True:
                dummy = str(int(setpoint))
            else:
                dummy = "{:.10f}".format(float(setpoint))
        except ValueError:
            dummy = str(setpoint)
        if signal is True:
            self.write("SET:" + address + ":SIG" + command + ":" + dummy)
        else:
            self.write("SET:" + address + command + ":" + dummy)
        return self.read()

    # utility functions
    def extractValueFromDict(self, entry):
        dummy = entry.split(":")[-1]
        dummy = re.findall(r"([+-]?(?:\d+(?:\.\d*)?)(?:[eE][-+]\d+)?)",
                           dummy)[0]
        try:
            return float(dummy)
        except TypeError:
            logger.debug("Type error during conversion of dict" +
                         " value {}".format(dummy[0]))
            return None

    def queryDict(self, queryDict, address="", signal=False):
        for key in queryDict:
            queryDict[key] = self.query_merc(key, address, signal)

    @synchronized
    def queryWorkingDict(self):
        for key in self.workingDict:
            dummy = self.query_merc(
                *self.workingDict[key][1:]).split(":")[-1].strip("\n")
            try:
                self.workingDict[key][0][0] = float(re.findall(
                    r"([+-]?(?:\d+(?:\.\d*)?)(?:[eE][-+]\d+)?)", dummy)[0])
            except (TypeError, IndexError):
                # If float conversion fails, try bool conversion
                if "ON" == dummy:
                    self.workingDict[key][0][0] = True
                elif "OFF" == dummy:
                    self.workingDict[key][0][0] = False
                else:
                    # what happened?
                    logger.info("Non bool value at " + str(key) +
                                " is " + dummy)

    def getDictValue(self, key):
        return self.workingDict[key][0][0]

    # status functions
    def queryAllDicts(self):
        self.queryID()
        self.querySysConf()
        self.queryTSensConf()
        self.queryTSensLoopConf()
        self.queryHeaterConf()
        self.queryTSensStatus()
        self.queryWorkingDict()

    def queryID(self):
        self.queryDict(self.idITC)

    def querySysConf(self):
        self.queryDict(self.sysDict, self.addressSys)

    def queryHeaterConf(self):
        self.queryDict(self.confDictHeater, self.addressHeater)

    def queryTSensLoopConf(self):
        self.queryDict(self.confDictTSensLoop, self.addressTSensLoop)

    def queryTSensConf(self):
        self.queryDict(self.confDictTSens, self.addressTSens)

    def queryTSensStatus(self):
        self.queryDict(self.dataDictTSens, self.addressTSens, True)

    def logAllDicts(self):
        logger.debug("ITC-ID: " + str(self.idITC))
        logger.debug("ITC-SYSCONF: " + str(self.sysDict))
        logger.debug("ITC-HEATERCONF: " + str(self.confDictHeater))
        logger.debug("ITC-TSENSCONF: " + str(self.confDictTSens))
        logger.debug("ITC-LOOPCONF: " + str(self.confDictTSensLoop))
        logger.debug("ITC-TSENSSTATUS: " + str(self.dataDictTSens))
        logger.debug("ITC-WORKING DICT: " + str(self.workingDict))

    # driver functions
    def setTVTI(self, val):
        # Limit TVTI to 300K
        if 0 > val:
            val = 0
        elif 300 < val:
            val = 300
        self.setVal(val, *self.workingDict["TSet"][1:])

    def getTVTI(self, setp=False):
        val = self.getDictValue("Temp")
        if setp is True:
            return (val, self.getDictValue("TSet"))
        else:
            return val

    def setNV(self, val):
        # Limit NV between 0 and 100%
        if 0 > val:
            val = 0
        elif 100 < val:
            val = 100
        self.setVal(val, *self.workingDict["FSet"][1:])

    def getNV(self):
        return self.getDictValue("FSet")

    def setAutoPID(self, val=True):
        if val is True:
            self.setVal("ON", *self.workingDict["APID"][1:])
        elif val is False:
            self.setVal("OFF", *self.workingDict["APID"][1:])

    def getAutoPID(self):
        return self.getDictValue("APID")

    def setAutoHTR(self, val=True):
        if val is True:
            self.setVal("ON", *self.workingDict["AHTR"][1:])
        elif val is False:
            self.setVal("OFF", *self.workingDict["AHTR"][1:])

    def getAutoHTR(self):
        return self.getDictValue("AHTR")

    def setPID(self, pid):
        for parm in pid:
            if 0 > parm:
                parm = 0
        self.setVal(pid[0], *self.workingDict["P"][1:])
        self.setVal(pid[1], *self.workingDict["I"][1:])
        self.setVal(pid[2], *self.workingDict["D"][1:])

    def getPID(self):
        return (self.getDictValue("P"),
                self.getDictValue("I"),
                self.getDictValue("D"))

    def setHeater(self, val):
        self.setVal(val, *self.workingDict["Heater"][1:])

    def getHeater(self):
        return self.getDictValue("Heater")
