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
"""Device driver for the Quantum Design PPMS."""

import time

import MultiPyVu as mpv
from wrapt import synchronized


class PPMS:
    """
    Class for interacting with the Quantum Design PPMS.

    The communication is handled by the MultiPyVu library.
    """

    def __init__(self, host, max_field, max_field_rate, max_temperature=400):
        """
        Initialize a PPMS device.

        Parameters
        ----------
        host : str
            The ip address and port where the device is located.
        max_field : float
            The maximum magnetic field in Tesla.
        max_field_rate : float
            The maximum magnetic field rate in Tesla/min.
        max_temperature : float, optional
            The maximum temperature in Kelvin. Defaults to 400.

        Attributes
        ----------
        MAX_FIELD : float
            Maximum field in Tesla.
        MAX_TEMPERATURE : float
            Maximum temperature in Kelvin.
        MAX_FIELD_RATE : float
            Maximum field rate in Tesla/min.
        """
        self.host = host

        self.MAX_FIELD = max_field  # max field in T
        self.MAX_TEMPERATURE = max_temperature
        self.MAX_FIELD_RATE = max_field_rate  # max field rate in T/min

        self._start = 0
        self._client = None

    def close(self):
        """Close the connection to the PPMS client."""
        if self._client is not None:
            self._client.close_client()

    @synchronized
    def _get_client(self):
        now = time.time()
        if (now - self._start) > 30 * 60:
            if self._client is not None:
                self._client.close_client()
            client = mpv.Client(host=self.host, socket_timeout=2)
            client.open()
            self._start = now
            self._client = client
            return client
        else:
            client = self._client
            return client

    def oersted2tesla(self, oersted):
        """
        Convert magnetic field strength from Oersted to Tesla.

        Parameters
        ----------
        oersted : float
            Magnetic field strength in Oersted.

        Returns
        -------
        tesla : float
            Magnetic field strength in Tesla.

        Notes
        -----
        1 Oe = 1e-4 T
        """
        return oersted * 1e-4

    def tesla2oersted(self, tesla):
        """
        Convert magnetic field strength from Tesla to Oersted.

        Parameters
        ----------
        tesla : float
            Magnetic field strength in Tesla.

        Returns
        -------
        oersted : float
            Magnetic field strength in Oersted.

        Notes
        -----
        1 T = 1e4 Oe
        """
        return tesla * 1e4

    def check_field_rate(self, rate):
        """
        Check and limit the field rate according to the currently set field.

        If the current field rate is higher than the allowed maximum, it is
        set to the maximum allowed value.

        Parameters
        ----------
        rate : float
            The desired magnetic field rate in Tesla/min.

        Returns
        -------
        float
            The adjusted magnetic field rate in Tesla/min, limited by MAX_FIELD_RATE.
        """
        rate = abs(rate)

        if rate > self.MAX_FIELD_RATE:
            rate = self.MAX_FIELD_RATE

        return rate

    def check_field(self, field):
        """
        Check if the magnetic field is within allowable limits.

        This function verifies whether the given field value is within the
        maximum allowable magnetic field strength defined by MAX_FIELD.

        Parameters
        ----------
        field : float
            The magnetic field strength in Tesla to be checked.

        Returns
        -------
        bool
            True if the field is within the permissible range, False otherwise.
        """
        if abs(field) > self.MAX_FIELD:
            return False
        else:
            return True

    @synchronized
    def set_field(self, setpoint, rate, persistent=False):
        """
        Set the magnetic field strength and optionally set it persistently.

        This function sets the magnetic field strength to the given setpoint
        and, if requested, sets it persistently. The field rate is checked
        against the maximum allowable value and the magnetic field strength
        is converted from Tesla to Oersted internally.

        Parameters
        ----------
        setpoint : float
            The magnetic field strength to be set in Tesla.
        rate : float
            The rate at which the magnetic field should change, in Tesla/min.
        persistent : bool, optional
            If True, the magnetic field is set persistently. Defaults to False.
        """
        if not self.check_field(setpoint):
            return

        rate = self.check_field_rate(rate)
        client = self._get_client()

        if persistent:
            driven_mode = client.field.driven_mode.persistent
        else:
            driven_mode = client.field.driven_mode.driven

        client.set_field(
            self.tesla2oersted(setpoint),
            self.tesla2oersted(rate) / 60,
            client.field.approach_mode.linear,
            driven_mode,
        )

    @synchronized
    def set_field_wait(self, setpoint, persistent=False):
        """
        Set the magnetic field strength and wait until it is reached.

        This function calls :meth:`set_field` and then waits until the magnetic
        field strength has reached the setpoint. The waiting time is limited to
        30 seconds and the function returns after this time has elapsed or if
        the magnetic field strength has reached the setpoint, whichever occurs
        first.

        Parameters
        ----------
        setpoint : float
            The magnetic field strength to be set in Tesla.
        persistent : bool, optional
            If True, the magnetic field is set persistently. Defaults to False.
        """
        self.set_field(setpoint, persistent)
        client = self._get_client()
        client.wait_for(0.1, 30000, client.field.waitfor)

    @synchronized
    def is_field_stable(self):
        """
        Check if the magnetic field is stable.

        Returns
        -------
        bool
            True if the field is stable, False otherwise.
        """
        client = self._get_client()
        return client.is_steady(client.field.waitfor)

    @synchronized
    def is_temperature_stable(self):
        """
        Check if the temperature is stable.

        Returns
        -------
        bool
            True if the temperature is stable, False otherwise.
        """
        client = self._get_client()
        return client.is_steady(client.temperature.waitfor)

    @synchronized
    def set_temperature_wait(self, setpoint):
        """
        Set the temperature and wait until it is reached.

        Parameters
        ----------
        setpoint : float
            The temperature to set in Kelvin.
        """
        self.set_temperature(setpoint)
        client = self._get_client()
        client.wait_for(1, 1000000, client.temperature.waitfor)

    @synchronized
    def get_field(self):
        """
        Retrieve the current magnetic field strength in Tesla.

        This function obtains the magnetic field strength from the MVclient,
        converts it from Oersted to Tesla, and returns the value.

        Returns
        -------
        float
            Magnetic field strength in Tesla.
        """
        client = self._get_client()
        field, _ = client.get_field()
        return self.oersted2tesla(field)

    @synchronized
    def get_field_status(self):
        """
        Retrieve the status of the magnetic field.

        Returns
        -------
        int
            Status of the magnetic field.
        """
        client = self._get_client()
        _, status = client.get_field()
        return status

    def check_temperature(self, temperature):
        """
        Check if the given temperature is within the maximum allowed range.

        Parameters
        ----------
        temperature : float
            Temperature in Kelvin.

        Returns
        -------
        bool
            True if the temperature is within the maximum allowed range,
            False otherwise.
        """
        if abs(temperature) >= self.MAX_TEMPERATURE:
            return False
        else:
            return True

    @synchronized
    def set_temperature(self, setpoint, rate):
        """
        Set the temperature setpoint.

        This function checks if the given setpoint is within the maximum
        allowable temperature range and, if so, sets the temperature setpoint
        using the MVclient. If the rate parameter is given, it is used to set the
        temperature ramp rate. Otherwise, the currently set ramp rate is used.

        Parameters
        ----------
        setpoint : float
            The temperature setpoint in Kelvin.
        rate : float
            The temperature ramp rate in Kelvin per minute.
        """
        if not self.check_temperature(setpoint):
            return

        client = self._get_client()
        client.set_temperature(
            setpoint,
            rate,
            client.temperature.approach_mode.fast_settle,
        )
        # When using the He3 option the temperature state goes to "unknown" for few seconds
        # if on e reads the temperature in this time interval multipyvu connection crashes.
        # we wait 5 seconds to prevent this problem
        time.sleep(5)

    @synchronized
    def get_temperature(self):
        """
        Retrieve the current temperature in Kelvin.

        Returns
        -------
        float
            Current temperature in Kelvin.
        """
        client = self._get_client()
        temperature, _ = client.get_temperature()
        return temperature

    @synchronized
    def get_temperature_status(self):
        """
        Retrieve the status of the temperature.

        Returns
        -------
        int
            Status of the temperature.
        """
        client = self._get_client()
        _, status = client.get_temperature()
        return status

    @synchronized
    def get_chamber_status(self):
        """
        Retrieve the current chamber status as a string.

        This function queries the MVclient for the current chamber status and
        returns the result as a string.

        Returns
        -------
        str
            Chamber status.
        """
        client = self._get_client()
        status = client.get_chamber()
        return status
