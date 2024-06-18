# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---
import configparser
import logging
import os.path
import sys
import tempfile
from datetime import date

# default datafile extension
output_extension = ".ma7"

# parse global default config
confparser = configparser.ConfigParser()

# read user configuration and local configuration if available
cfiles = confparser.read([
    os.path.expanduser(os.path.join("~", ".matr1x.conf")),
    "matr1x.conf"])

datetimefmt = confparser.get("matr1x", "datetime_format",
                             fallback="%Y-%m-%dT%H:%M:%S")

# load setting for the execution path of matrix-script scripts. With the default
# value of None this will be the directory in which matrix-script was started.
# Using the start menu integration this typically is the home folder of the
# current user. Alternatively it can be the directory in which '*.matrix' file
# is stored ("<script-location>") or any valid folder.
matrix_script_execution_path = confparser.get("matr1x", "script-path",
                                              fallback=None)
if matrix_script_execution_path not in (None, "<script-location>"):
    if not os.path.exists(matrix_script_execution_path):
        matrix_script_execution_path = None

usersfolder = os.path.expanduser(confparser.get("matr1x", "usersDirectory",
                                 fallback=os.path.join('~', 'users')))
if not os.path.exists(usersfolder):
    usersfolder = os.path.expanduser("~")

systems_directory = os.path.expanduser(
    confparser.get("matr1x", "systemsDirectory", fallback="<pkgroot>/systems"))

# replace pkgroot placeholder if present
if "<pkgroot>/" in systems_directory:
    systems_directory = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        systems_directory.replace("<pkgroot>/", ""))
# expand eventual home
systems_directory = os.path.expanduser(systems_directory)

# set up logging, mostly for debugging purposes.
# Verbose logs can be produced by changing logging.INFO to logging.DEBUG. This
# is however not recommended in production environments.
logfolder = os.path.expanduser(
    confparser.get("matr1x", "loggingDirectory",
                   fallback=os.path.join('~', 'logs')))
kwargs = dict(level=logging.INFO,
              format='%(asctime)s,%(msecs)03d,%(levelname)s,%(name)s: %(message)s',
              datefmt=datetimefmt)
handlers = []
if not os.path.exists(logfolder):
    logfolder = tempfile.gettempdir()  # set logfolder to temp directory
    if sys.stdout is not None:
        # if logging to temp directory also log to stdout
        handlers.append(logging.StreamHandler(stream=sys.stdout))

today = date.today().isocalendar()
if sys.version_info.major == 3 and sys.version_info.minor < 9:
    from collections import namedtuple
    datetuple = namedtuple("Isocalendar", ["year", "week", "weekday"])
    today = datetuple(*today)
handlers.append(logging.FileHandler(
    os.path.join(logfolder, f'matr1x_{today.year}{today.week:02d}.log'),
    mode='a'))

kwargs["handlers"] = handlers
logging.basicConfig(**kwargs)
