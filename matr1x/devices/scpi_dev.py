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

import ast
import pickle
import re
import time

from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import strict_discrete_set

from matr1x.util import Get, normalize_cmds


def makeSCPIdevice(*cmds, system=True):
    """
    dynamically generate a pymeasure device which can be used in systems to
    connect to the SCPI commands

    Parameters
    ----------
    cmds: dict
      multiple dictionaries with commands. Those will be merged internally and
      therefore must only contain unique keys.
    system: bool
      flag to decide if config_params shall be defined on the device
    """
    typeplaceholder = {int: "%d", float: "%g", bool: "%d",
                       str: "%s", None: ""}

    cmd_list = {}
    # merge commands in arguments
    for entry in cmds:
        normalize_cmds(entry)
        cmd_list.update(entry)

    def make_identifier(s):
        """create valid Python identifier by omitting invalid characters"""
        # Remove invalid characters
        s = re.sub('[^0-9a-zA-Z_]', '', s)
        # Remove leading characters until we find a letter or underscore
        s = re.sub('^[^a-zA-Z_]+', '', s)
        return s

    def strict_length(value, values):
        """pymeasure validator to enforce array length"""
        if len(value) != values:
            raise ValueError(
                f"Value {value} does not have an appropriate length of {values}")
        return value

    def list2str(value, dtype):
        ret = []
        for v, dt in zip(value, dtype):
            if dt is bool:
                ret.append(typeplaceholder[int] % v)
            else:
                ret.append(typeplaceholder[dt] % v)
        return ",".join(ret)

    def castlist(values, dtype):
        ret = []
        for v, t in zip(values, dtype):
            if t is bool:
                if v == 'False':
                    castval = False
                elif v == 'True':
                    castval = True
                else:
                    castval = None
            else:
                castval = t(v)
            ret.append(castval)
        return ret

    def constructor(self, adapter, name='clientdevice', **kwargs):
        """constructor for an object derived from pymeasure Instrument"""
        kwargs.update(read_termination='\n',
                      write_termination='\n',
                      includeSCPI=False)
        Instrument.__init__(self, adapter, name, **kwargs)

    def query(self, cmd):
        """query function, needs to be present to work with system"""
        return self.ask(cmd)

    def check_set_errors(self):
        reply = self.read()
        if reply != '\x06':
            raise ValueError(
                "Wrong reply received when there should be an acknowledge.")
        return []

    def create_setnwait(attr, pollattr):
        """return a set and wait method which can be used in system files"""

        def setnwait(self, value):
            setattr(self, attr, value)
            while not getattr(self, pollattr):
                time.sleep(0.1)
        return setnwait

    def create_parameterless(cmd):
        """return a parameterless function, which triggers the corresponding
        set"""

        def parameterless(self, cmd=cmd):
            Instrument.write(self, cmd)
            check_set_errors(self)
        return parameterless

    def id(self):  # noqa: A001  # use pymeasure Instrument.id
        """Get the identification of the Instrument."""
        return self.idn

    attributes = dict()
    methods = {"__init__": constructor,
               "query": query,
               "id": id,
               "check_set_errors": check_set_errors,
               }

    # make id standard config parameter
    attributes["config_params"] = {"id": "idn"}

    # add system query to config_params
    if system and ":conf" not in cmd_list:
        attributes["config_params"]["SCPIdevconf"] = "conf"
        cmd_list[":conf"] = Get(
            lambda b: pickle.loads(ast.literal_eval(b)),
            True
        )

    for name, cmd in cmd_list.items():
        # create an pymeasure attribute for every command
        att = make_identifier(name)
        try:
            stringplaceholder = typeplaceholder[cmd.dtype]
        except (KeyError, TypeError):
            if isinstance(cmd.dtype, (tuple, list)):
                stringplaceholder = '%s'
            elif cmd.setfunc is not None:
                raise

        kwargs = {}
        if isinstance(cmd.dtype, (tuple, list)):
            kwargs['cast'] = lambda x: x  # noop, handled in get_process
            kwargs['validator'] = strict_length
            kwargs['values'] = len(cmd.dtype)
            kwargs['set_process'] = lambda v, t=cmd.dtype: list2str(v, t)
            kwargs['get_process'] = lambda v, t=cmd.dtype: castlist(v, t)
        elif cmd.dtype == bool:
            kwargs['validator'] = strict_discrete_set
            kwargs['values'] = [True, False, None]
            kwargs['get_process'] = lambda s: castlist([s, ], [bool, ])[0]
            kwargs['set_process'] = int
        else:
            kwargs['cast'] = cmd.dtype

        if cmd.setfunc is None:
            if "validator" in kwargs:
                # for pure get property some kwargs are not allowed
                del kwargs["validator"]
                del kwargs["set_process"]
            attributes[att] = Instrument.measurement(
                name + '?', f"get {att}", **kwargs)
        elif cmd.getfunc is None:
            if cmd.dtype is None:
                # create parameterless functions (e.g. trigger)
                methods[f'{att}'] = create_parameterless(name)
            else:
                kwargs['check_set_errors'] = True
                attributes[att] = Instrument.setting(
                    name + f' {stringplaceholder}', f"set {att}", **kwargs)
        else:  # here both setfunc and getfunc are real
            kwargs['check_set_errors'] = True
            attributes[att] = Instrument.control(
                name + '?', name + f' {stringplaceholder}',
                f"get/set {att}", **kwargs)
        # create set and wait/poll method in case this is asked for
        if cmd.polling_cmd is not None:
            methods[f'set_{att}'] = create_setnwait(
                att, make_identifier(cmd.polling_cmd))

    methods.update(attributes)

    return type("SCPIdevice", (Instrument, ), methods)
