import configparser
import logging
import os.path
import sys
import tempfile
from datetime import date

# parse global default config
confparser = configparser.ConfigParser()

# read user configuration and local configuration if available
cfiles = confparser.read([
    os.path.expanduser(os.path.join("~", ".matr1x.conf")),
    "matr1x.conf"])

datetimefmt = confparser.get("matr1x", "datetime_format",
                             fallback="%Y-%m-%dT%H:%M:%S")

systems_directory = confparser.get("matr1x", "systemsDirectory",
                                   fallback="<pkgroot>/systems")
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
today = date.today().isocalendar()
logfolder = confparser.get(
    "matr1x", "loggingDirectory",
    fallback=os.path.join(os.path.expanduser('~'), 'logs'))
kwargs = dict(level=logging.INFO,
              format='%(asctime)s,%(msecs)03d,%(levelname)s,%(name)s: %(message)s',
              datefmt=datetimefmt)
if os.path.exists(logfolder):
    kwargs["filename"] = os.path.join(
        logfolder, 'matr1x_' + str(today[0]) + str(today[1]) + '.log')
    kwargs["filemode"] = 'a'
else:
    logfolder = tempfile.gettempdir()  # set logfolder to temp directory
    if sys.stdout is not None:
        kwargs["stream"] = sys.stdout
logging.basicConfig(**kwargs)
