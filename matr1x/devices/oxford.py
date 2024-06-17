# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---
import logging
import math
import time

from pyvisa import constants, errors
from wrapt import synchronized

from .visadevice import VisaDevice

logger = logging.getLogger(__name__)


class IsobusDevice(VisaDevice):
    """
    class to be used to derive Oxford Instruments device drivers.
    """

    def __init__(self, interface, **kwargs):
        self.isobus_addr = kwargs.pop("isobus_addr", None)
        if "query_delay" not in kwargs:
            kwargs["query_delay"] = 0.05
        super().__init__(interface, **kwargs)

    def id(self):
        return self.query("V")

    @synchronized
    def write(self, msg):
        """add isobus address to mesage if it is set"""
        if self.isobus_addr is not None:
            if msg.startswith("$"):
                cmd = f"$@{self.isobus_addr}{msg[1:]}"
            else:
                cmd = f"@{self.isobus_addr}{msg}"
        else:
            cmd = msg
        super().write(cmd)

    @synchronized
    def query(self, msg, depth=0):
        with self.sharedlock:
            time.sleep(3*depth)  # add progressive delay on repeated failure
            self.read_very_eager()
            if depth > 10:
                logger.info(
                    f"{self.name}.query: maximum depth exeeded ('{msg}')")
                self.read_very_eager()
                if msg == 'X':
                    return 'X00000000000000'
                else:
                    return f"{msg[0]}0.00"
            if self.isobus_addr is not None:
                cmd = f"@{self.isobus_addr}{msg}"
            else:
                cmd = msg
            try:
                ret = super().query(cmd)
            except UnicodeDecodeError:
                logger.info(
                    f"{self.name}.query: UnicodeDecodeError, {msg}, {depth}")
                return self.query(msg, depth+1)
            except errors.VisaIOError:
                logger.info(
                    f"{self.name}.query: VisaIOError, {msg}, {depth}")
                return self.query(msg, depth+1)

            if ret is None:
                logger.info(f"{self.name}.query: None, {msg}, {depth}")
                ret = self.query(msg, depth+1)
            if "?" in ret:
                logger.info(f"{self.name}.query: reply '?', {msg}, {depth}")
                ret = self.query(msg, depth+1)
            elif "" == ret:
                logger.info(
                    f"{self.name}.query: empty reply, {msg}, {depth}")
                ret = self.query(msg, depth+1)
            elif msg[0] not in ret:
                logger.info(
                    f"{self.name}.query: wrong reply character, {msg}, {depth}, {ret}")
                try:
                    self.read_very_eager()
                except UnicodeDecodeError:
                    pass
                ret = self.query(msg, depth+1)
            return ret

    @synchronized
    def query_float(self, msg, depth=0):
        """routine to query a float including error checking"""
        with self.sharedlock:
            ret = self.query(msg, depth)
            try:
                return float(ret[1:])
            except ValueError:
                logger.info(
                    f"{self.name}.query_float: float conversion error ('{msg}', {ret})")
                # retry query
                return self.query_float(msg, depth+1)


class ILM200(IsobusDevice):
    """
    Driver for Oxford ILM200 series level meter.
    """
    config_params = {"LHe": "getLHe",
                     "LN2": "getLN2"}

    def __init__(self, interface, isobus_addr=None, **kwargs):
        kwargs["isobus_addr"] = isobus_addr
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 2000
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 10
        if "stop_bits" not in kwargs:
            kwargs["stop_bits"] = constants.StopBits.two
        super().__init__(interface, **kwargs)
        self.query("C3")

    def getLHe(self):
        return self.query_float('R1') / 10

    def getLN2(self):
        return self.query_float('R2') / 10

    def setRate(self, fast):
        """
        if fast is true, set rate to fast
        """
        if fast is True:
            self.query("T1")
        else:
            self.query("S1")

    def getRate(self):
        for depth in range(11):
            ret = self.query("X", depth)
            try:
                state = bool(int(ret[6], 16) & 0b10)
                break
            except (ValueError, IndexError):
                logger.debug("index 6 not convertible to int, {}".format(ret))
        return state


class ITC503(IsobusDevice):
    """
    implements the command communication of a ITC503.
    """
    config_params = {"AutoHeater": "getAutoHeater",
                     "PID": "getPID"}

    def __init__(self, interface, isobus_addr=None, **kwargs):
        kwargs["isobus_addr"] = isobus_addr
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 2000
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 10
        if "stop_bits" not in kwargs:
            kwargs["stop_bits"] = constants.StopBits.two
        super().__init__(interface, **kwargs)
        self.query("C3")

    def setTVTI(self, temp):
        self.write(f'$T{temp:.2f}')

    def getTVTI(self, setp=False, channel=1):
        temp = self.query_float('R{:d}'.format(channel))
        if setp is False:
            return temp
        else:
            temps = self.query_float('R0')
            return [temp, temps]

    def setHeater(self, htr):
        self.write(f'$O{float(htr):.1f}')

    def getHeater(self):
        return self.query_float('R5')

    def setAutoHeater(self, ahtr):
        ahtr = int(bool(ahtr))
        self.write(f'$A{ahtr:d}')

    def getAutoHeater(self):
        for depth in range(11):
            ret = self.query('X', depth)
            try:
                astat = int(ret[3])
                break
            except (IndexError, ValueError):
                logger.debug(f"index 3 not convertible to int, {ret}")
                astat = 0
        if astat in (1, 3):
            return True
        else:
            return False

    def setNV(self, nv):
        nv = float(nv)
        if nv > 99.9:
            nv = 99.9
        elif nv < 0:
            nv = 0
        self.write(f'$G{nv:.1f}')

    def getNV(self):
        return self.query_float('R7')

    def getPID(self):
        ret = []
        for rnum in (8, 9, 10):
            ret.append(self.query_float('R{:d}'.format(rnum)))
        return ret

    def setPID(self, pid):
        for cmd, val, digits in zip(('P', 'I', 'D'), pid, (3, 1, 1)):
            self.query("{}{}".format(cmd, str(round(val, digits))))


class IPS120(IsobusDevice):
    """
    Driver for IPS120 or Mercury-IPS in IPS120 mode
    """
    config_params = {"Rate": "getMagneticFieldRate",
                     "MagnetStatus": "getMagnetStatus"}

    def __init__(self, interface, isobus_addr=None, field_lim=0, **kwargs):
        self.field_lim = field_lim
        kwargs["isobus_addr"] = isobus_addr
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 2000
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 5
        if "stop_bits" not in kwargs:
            kwargs["stop_bits"] = constants.StopBits.two
        if "query_delay" not in kwargs:
            kwargs["query_delay"] = 0.2
        super().__init__(interface, **kwargs)
        self.query("C3")

    def setMagneticField(self, xval):
        """
        Sets the magnetic field to "xval" on the x axis,

        Arguments:
            xval:float

        Additionally checks, that all values are within the boundaries
        """
        # check field limits
        if self.field_lim < xval:
            xval = self.field_lim
        elif -self.field_lim > xval:
            xval = -self.field_lim
        self.query("J{:.4f}".format(xval))

    def getMagneticFields(self, setp=False):
        """
        Returns the values of the magnetic field

        Arguments:
            setp:bool - if setp is true, returns also the setpoints
        """
        fval = self.query_float("R7")
        if setp is True:
            setpoint = self.query_float("R8")
            return ([fval], [setpoint])
        else:
            return [fval]

    def setMagneticFieldRate(self, rate, axis):
        """
        Set rate of magnetic axis "axis" to "rate"

        Arguments:
            rate:float - can be between 0 and 0.5T/min
            axis:integer - 0=x
        """
        if 0 > rate:
            rate = 0
        elif 0.5 < rate:
            rate = 0.5
        if -1 == axis:
            self.query("T{:.4f}".format(rate[0]))
        if 0 == axis:
            self.query("T{:.4f}".format(rate))

    def getMagneticFieldRate(self, axis, setp=False):
        """
        Get rate of the magnetic axis "axis"

        Arguments:
            axis:integer - 0=x
            setp:bool - If setp is true, also returns the setpoint
        """
        if -1 == axis:
            val = [self.query_float("R9")]
            if setp is True:
                val += [self.query_float("R9")]
        elif 0 == axis:
            val = self.query_float("R9")
            if setp is True:
                val = (val, self.query_float("R9"))
        return val

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
        if -1 == axis:
            self.query("A{:d}".format(state[0]))
        elif 0 == axis:
            self.query("A{:d}".format(state))

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
        for depth in range(11):
            ret = self.query("X", depth)
            try:
                state = int(ret[4])
                break
            except (ValueError, IndexError):
                logger.debug("index 4 not convertible to int, {}".format(ret))
        if -1 == axis:
            return [state]
        elif 0 == axis:
            return state


class IPS120_switchheater(IsobusDevice):
    """
    Driver for IPS120 (legacy without floats as in OSCAR or with floats as in blue cryo)
    """
    config_params = {"Rate": "getMagneticFieldRate",
                     "MagnetStatus": "getMagnetStatus",
                     "SwitchHeater": "getSwitchHeater"}

    def __init__(self, interface, isobus_addr=None, legacy=True,
                 fieldlimits=(0, 1), max_rate=0.5, switch_wait_time=5,
                 **kwargs):
        self.persistentField = None
        self.legacy = legacy
        self.fieldlimits = fieldlimits
        self.switch_wait_time = switch_wait_time
        self.max_rate = max_rate
        self.statusmsg = ""
        kwargs["isobus_addr"] = isobus_addr
        kwargs["open"] = open
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 2000
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 10
        if "stop_bits" not in kwargs:
            kwargs["stop_bits"] = constants.StopBits.two
        if "query_delay" not in kwargs:
            kwargs["query_delay"] = 0.2
        super().__init__(interface, **kwargs)
        self.query("C3")
        self.persistentField = self.getPersistentField()

    def _update_sleep(self, sec, msg=None, interval=0.5):
        """
        waits for "sec" seconds (or up to "interval" more) while updating the
        internal status message. The message can contain one placeholder "{}"
        which will be replaced by the remaining waiting time
        """
        t0 = time.time()
        if msg is None:
            msg = "waiting {:2.0f} s"
        while (time.time() - t0) < sec:
            stillwaiting = sec - (time.time() - t0)
            if stillwaiting > interval*1.1:
                self.statusmsg = msg.format(stillwaiting)
                time.sleep(interval)
            else:
                time.sleep(stillwaiting)
                break
            self.statusmsg = ""

    # driver functions
    def setMagneticField(self, xval):
        """
        Sets the magnetic field to "xval" on the x axis,

        Arguments:
            xval:float

        Additionally checks, that all values are within the boundaries
        """
        # check xval <= fieldlimits
        if self.fieldlimits[1] < xval:
            xval = self.fieldlimits[1]
        elif self.fieldlimits[0] > xval:
            xval = self.fieldlimits[0]
        if self.legacy:
            self.query("J{:d}".format(int(1000*xval)))
        else:
            self.query("J{:.4f}".format(xval))

    def getMagneticField(self, setp=False):
        """
        Returns the values of the magnetic field

        Arguments:
            setp:bool - if setp is true, returns also the setpoints
        """
        if self.legacy:
            fval = self.query_float("R7") / 1000
            if setp is True:
                return (fval, self.query_float("R8") / 1000)
        else:
            fval = self.query_float("R7")
            if setp is True:
                return (fval, self.query_float("R8"))
        return fval

    def getPersistentField(self):
        """
        Returns the persistent field value, only
        returns valid value if switch heater is off
        otherwise persistent field is 0
        """
        if self.getSwitchHeater() in (0, 2):
            self.persistentField = self.query_float("R18")
            if self.legacy:
                self.persistentField /= 1000
        else:
            self.persistentField = None
        return self.persistentField

    @synchronized
    def setMagneticFieldNonPersistent(self, field, block=False):
        """
        sets the field but leaves switch heater on
        """
        # verify magnet is in non persistent mode first
        swhtr = self.getSwitchHeater()
        if 2 == swhtr:
            # magnet is persistent with field inside, first remove field
            # set magnet on hold
            self.setMagnetStatus(0)
            time.sleep(0.1)
            # set setpoint to persistent field value
            self.setMagneticField(self.getPersistentField())
            time.sleep(0.1)
            # set magnet to go to setpoint
            self.setMagnetStatus(1)
            while (self.persistentField != self.getMagneticField()):
                time.sleep(1)
            time.sleep(1)
            # now magnet is ready to be switched to non persistent mode
            # turn on switch heater
            self.setSwitchHeater(True)
            # now magnet is in non persistent mode
        elif 0 == swhtr:
            # switch heater is off but no field in magnet
            # turn on switch heater
            self.setSwitchHeater(True)
            # now magnet is in non persistent mode
        else:
            # switch heater is on anyway
            pass
        # set magnet to hold
        self.setMagnetStatus(0)
        time.sleep(0.1)
        # apply setpoint
        self.setMagneticField(field)
        time.sleep(0.1)
        # set to go to setpoint and remain there
        self.setMagnetStatus(1)
        # switch heater stays on
        self.statusmsg = f"Ramping to {field} T"
        if block:
            while True:
                current_field = self.getMagneticField()
                # wait for magnet to reach setpoint
                if math.isclose(field, current_field, abs_tol=0.0001):
                    # # wait for magnet hold mode after reaching setpoint
                    # if self.getMagnetStatus() == 0:
                    break
                time.sleep(1)
            self.statusmsg = ""

    @synchronized
    def setMagneticFieldPersistent(self, field):
        """
        sets the field and goes into persistent mode
        """
        self.setMagneticFieldNonPersistent(field, block=True)
        # wait to be certain all field is gone
        time.sleep(1)
        # turn off switch heater
        self.setSwitchHeater(False)
        # set non persistent field to 0
        self.setMagnetStatus(2)
        # update persistent field in local memory
        self.getPersistentField()

    def setMagneticFieldRate(self, rate):
        """
        Set rate to "rate"

        Arguments:
            rate:float - can be between 0 and max_rate T/min
        """
        if 0 > rate:
            rate = 0
        elif self.max_rate < rate:
            rate = self.max_rate
        if self.legacy:
            self.query("T{:04d}".format(int(rate*1000)))
        else:
            self.query("T{:.4f}".format(rate))

    def getMagneticFieldRate(self, setp=False):
        """
        Get rate of the magnetic field

        Arguments:
            setp:bool - If setp is true, also returns the setpoint
        """
        if self.legacy:
            val = self.query_float("R9") / 1000
            if setp is True:
                val = (val, self.query_float("R9") / 1000)
        else:
            val = self.query_float("R9")
            if setp is True:
                val = (val, self.query_float("R9"))
        return val

    def getVersion(self):
        return self.query("V")

    def getVoltage(self):
        """
        Returns the values of the power supply output voltage
        """
        if self.legacy:
            return self.query_float("R1") / 100
        else:
            return self.query_float("R1")

    @synchronized
    def setMagnetStatus(self, state):
        """
        Set state status of the magnet to state, where state can be 0 to 3

        Arguments:
            state:integer - offers the following options:
                0 - HOLD
                1 - RTOS (Ramp to setpoint)
                2 - RTOZ (Ramp to zero)
                3 - CLMP (Clamped, when current is 0) - disallowed
        """
        try:
            state = int(state)
            if 2 < state:
                # do NOT set to 3, opens door to breaking magnet!
                return
            elif 0 > state:
                return
        except ValueError:
            return
        self.query("A{:d}".format(state))

    def getMagnetStatus(self):
        """ Get status of the magnet

        Arguments:

        Returns:
            state of the magnet (0-3):
                0 - HOLD
                1 - RTOS (Ramp to setpoint)
                2 - RTOZ (Ramp to zero)
                3 - CLMP (Clamped, when current is 0)
                4 - Warming up
                8 - Fault
        """
        for depth in range(11):
            ret = self.query("X", depth)
            try:
                state = int(ret[4])
                break
            except (ValueError, IndexError):
                logger.debug("index 4 not convertible to int, {}".format(ret))
        return state

    def setSwitchHeater(self, output):
        """
        If output is True: Turn on the switch heater if magnet
        current is already set
        """
        if output is True:
            self.query("H1")
            self._update_sleep(self.switch_wait_time,
                               "warming the switch ({:2.0f} s)")
        else:
            self.query("H0")
            self._update_sleep(self.switch_wait_time,
                               "cooling the switch ({:2.0f} s)")

    def getSwitchHeater(self):
        """
        Returns state of switch heater
        0 is Off with no field in the magnet
        1 is On
        2 is Off with persistent field inside
        5 is heater fault
        8 is no switch fitted
        """
        for depth in range(11):
            ret = self.query("X", depth)
            try:
                state = int(ret[8])
                break
            except (ValueError, IndexError):
                logger.debug("index 8 not convertible to int, {}".format(ret))
        return state
