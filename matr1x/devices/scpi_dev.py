import ast
import copy
import pickle
import re
import time
from operator import attrgetter

from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import strict_discrete_set


def set_cmd_funcs(cls, cmd_list, sys=None):
    """
    setter and getter functions are replaced by the respective class methods
    or device functions from the system
    """
    # avoid in-place replacement of cmd_list
    out_list = copy.deepcopy(cmd_list)
    for cmd in out_list:
        for i in (1, 3):  # for setter and getter
            attrname = out_list[cmd][i]
            if attrname is not None and not callable(attrname):
                if isinstance(attrname, str):  # class property or function
                    attr = attrgetter(attrname)(cls)
                    if not callable(attr) and i == 1:
                        out_list[cmd][i] = lambda value, c=cls, a=attrname: setattr(
                            c, a, value)
                    elif not callable(attr) and i == 3:
                        out_list[cmd][i] = cls.__getattribute__
                        out_list[cmd][i+1] = [attrname, ]
                    else:
                        out_list[cmd][i] = attr
                elif isinstance(attrname, (tuple, list)):  # system device name and method
                    if sys is None:
                        raise ValueError(
                            "System must be specified as third argument")
                    devname, funcname = attrname
                    func = attrgetter(funcname)(sys.devs[devname])
                    out_list[cmd][i] = func
    return out_list


def makeSCPIdevice(cmd_list, sys=None):
    """
    dynamically generate a pymeasure device which can be used in systems to
    connect to the SCPI commands
    """
    typeplaceholder = {int: "%d", float: "%g", bool: "%d",
                       str: "%s", ast.literal_eval: "%s", None: ""}

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
            if dt == bool:
                ret.append(typeplaceholder[int] % v)
            else:
                ret.append(typeplaceholder[dt] % v)
        return ",".join(ret)

    def castlist(values, dtype):
        ret = []
        for v, t in zip(values, dtype):
            if t == bool:
                castval = False if v == 'False' else True
            else:
                castval = t(v)
            ret.append(castval)
        return ret

    def constructor(self, adapter, name='clientdevice', **kwargs):
        """constructor for an object derived from pymeasure Instrument"""
        kwargs.update(read_termination='\n',
                      write_termination='\n', includeSCPI=False)
        Instrument.__init__(self, adapter, name, **kwargs)

    def query(self, cmd):
        """query function, needs to be present to work with system"""
        return self.ask(cmd)

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
        return parameterless

    def id(self):
        """ return idn """
        return self.idn

    attributes = dict()
    methods = {"__init__": constructor, "query": query, "id": id}

    # make id standard config parameter
    attributes["config_params"] = {"id": "idn"}

    # add system query to config_params
    if sys:
        attributes["config_params"]["SCPIdevconf"] = "conf"
        cmd_list[":conf"] = [ast.literal_eval,
                             None, [],
                             lambda: pickle.dumps(sys.query()), []]

    # add system query to config_params
    if sys:
        attributes["config_params"] = {"SCPIdevconf": "conf"}
        cmd_list[":conf"] = [ast.literal_eval,
                             None, [],
                             lambda: pickle.dumps(sys.query()), []]

    for cmd in cmd_list:
        # create an pymeasure attribute for every command
        dtype, setfunc, setargs, getfunc, getargs = cmd_list[cmd][:5]

        att = make_identifier(cmd)

        try:
            stringplaceholder = typeplaceholder[dtype]
        except TypeError:
            if isinstance(dtype, (tuple, list)):
                stringplaceholder = '%s'
            else:
                raise
        except KeyError:
            if setfunc is not None:
                raise

        kwargs = dict()
        if isinstance(dtype, (tuple, list)):
            kwargs['cast'] = lambda x: x  # noop, handled in get_process
            kwargs['validator'] = strict_length
            kwargs['values'] = len(dtype)
            kwargs['set_process'] = lambda v, t=dtype: list2str(v, t)
            kwargs['get_process'] = lambda v, t=dtype: castlist(v, t)
        elif dtype == bool:
            kwargs['validator'] = strict_discrete_set
            kwargs['values'] = [True, False]
            kwargs['get_process'] = lambda s: False if s == 'False' else True
            kwargs['set_process'] = int
        elif dtype == ast.literal_eval:
            kwargs['cast'] = lambda x: x  # noop, handled in get_process
            kwargs['get_process'] = lambda b: pickle.loads(ast.literal_eval(b))
        else:
            kwargs['cast'] = dtype

        if setfunc is None:
            attributes[att] = Instrument.measurement(
                cmd + '?', f"get {att}", **kwargs)
        elif getfunc is None:
            if dtype is None:
                # create parameterless functions (e.g. trigger)
                methods[f'{att}'] = create_parameterless(cmd)
            else:
                attributes[att] = Instrument.setting(
                    cmd + f' {stringplaceholder}', f"set {att}", **kwargs)
        else:  # here both setfunc and getfunc are real
            attributes[att] = Instrument.control(cmd + '?', cmd + f' {stringplaceholder}',
                                                 f"get/set {att}", **kwargs)
        # create set and wait/poll method in case this is asked for
        if len(cmd_list[cmd]) > 5:
            methods[f'set_{att}'] = create_setnwait(
                att, make_identifier(cmd_list[cmd][5]))

    methods.update(attributes)

    return type("SCPIdevice", (Instrument, ), methods)
