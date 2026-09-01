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
"""
Contains utility functions for generating control GUIs or devices.

This module provides functionality for creating control graphical user
interfaces or devices based on the scpi_tcp_server.
"""

import logging
import mimetypes
import numbers
import os
import smtplib
import ssl
import sys
import time
from collections.abc import Sequence
from email import encoders
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from subprocess import PIPE, Popen
from typing import TYPE_CHECKING, Any

import numpy
import psutil
from numpy.typing import ArrayLike
from PySide6.QtCore import (
    QStandardPaths,
)
from PySide6.QtWidgets import (
    QMessageBox,
    QWidget,
)

if TYPE_CHECKING:
    from matr1x.control.controlwindow import ControlWindow


from .. import config
from ..error_handling import install_error_handler
from ..gui.error_dialog import install_qt_error_dialog
from ..gui_util import MApplication

# Re-exports for backwards compatibility (the code now lives in gui_dict /
# widgets). Kept so existing `from matr1x.control.util import ...` works.
from .gui_dict import (
    GuiDict,
    MethodBundle,
    catchEmitError,
    guiObject,
    var,
)
from .widgets import MyQDockWidget

__all__ = [
    "GuiDict",
    "MethodBundle",
    "MyQDockWidget",
    "catchEmitError",
    "control_main",
    "guiObject",
    "linear_trend",
    "sendNotificationEmail",
    "var",
]

logger = logging.getLogger(__name__)


def linear_trend(
    timestamps: ArrayLike, data: ArrayLike, interval: float = 60
) -> tuple[float | None, float | None]:
    """
    Calculate the linear trend of the data in the last 'interval' seconds.

    Parameters
    ----------
    timestamps : array-like
        time stamps of data in Unix-time in seconds (e.g. from `time.time()`)
    data : array-like
        past data points (most recent data point has index 0!).
        shape is assumed to be same for the two arguments
    interval : float, optional
        time interval of the data points which should be considered. Older data
        points are ignored.

    Note
    ----
    Best use collections.deque and appendleft to generate the needed data

    Returns
    -------
    slope, stdev
        slope and standard deviation of past `interval` seconds. If there are
        insufficient data points to calculate the statistics each value will be
        `None`.
    """
    ret = (None, None)
    mask = (time.time() - numpy.asarray(timestamps)) < interval
    t, y = numpy.asarray(timestamps)[mask], numpy.asarray(data)[mask]
    if len(t) >= 2 and numpy.all([isinstance(el, numbers.Number) for el in y]):
        slope = numpy.mean(numpy.gradient(y, t))
        std = numpy.std(y)
        ret = (slope, std)
    return ret


def _create_email_attachment(filename: str | Path) -> MIMEBase | None:
    """Create a MIME attachment for a file, or return ``None`` if it is absent."""
    fpath = Path(filename)
    if not fpath.is_file():
        return None

    ctype, encoding = mimetypes.guess_type(fpath)
    if ctype is None or encoding is not None:
        ctype = "application/octet-stream"
    maintype, subtype = ctype.split("/", 1)

    if maintype == "text":
        with fpath.open() as fp:
            attachment = MIMEText(fp.read(), _subtype=subtype)
    elif maintype == "image":
        with fpath.open("rb") as fp:
            attachment = MIMEImage(fp.read(), _subtype=subtype)
        attachment.add_header("Content-ID", f"<{fpath.name}>")
    elif maintype == "audio":
        with fpath.open("rb") as fp:
            attachment = MIMEAudio(fp.read(), _subtype=subtype)
    else:
        with fpath.open("rb") as fp:
            attachment = MIMEBase(maintype, subtype)
            attachment.set_payload(fp.read())
        encoders.encode_base64(attachment)

    attachment.add_header("Content-Disposition", "attachment", filename=fpath.name)
    return attachment


def sendNotificationEmail(
    address: str, subject: str, msgtext: str, attachments: list[str | Path] | None = None
) -> None:
    """
    Send messages to a list of email addresses.

    Utility function that uses the sendmail command line function which has to
    be configured to work as intended.

    Parameters
    ----------
    address : str
        email adress(es) in a comma seperated list
    subject : str
        email subject
    msgtext : str
        email message, can contain HTML code including img-tags
        (-> attach the image file)
    attachments: list
        list of file names of things to attach to the email.
    """
    # a check for valid email adresses should be added here!
    if address == "":
        return
    msg = MIMEMultipart()
    msg["To"] = address
    msg["Subject"] = subject
    mimetxt = MIMEText(msgtext, "html")
    msg.attach(mimetxt)
    for filename in attachments or []:
        attachment = _create_email_attachment(filename)
        if attachment is not None:
            msg.attach(attachment)

    # read email config
    conf = config.matr1x.email
    context = ssl.create_default_context()

    try:
        if (
            conf.smtp_server is not None
            and conf.smtp_user is not None
            and conf.fromemail is not None
            and conf.password is not None
        ):
            with smtplib.SMTP_SSL(conf.smtp_server, conf.smtp_port, context=context) as server:
                server.login(conf.smtp_user, conf.password)
                server.send_message(msg, from_addr=conf.fromemail, to_addrs=address)
        elif os.name == "posix":
            p = Popen(["sendmail", "-t"], stdin=PIPE)
            p.communicate(msg.as_bytes())
            p.wait()
            logger.info("notification email %s sent to %s", msgtext, address)
        else:
            logger.error("no email configuration found; see documentation on how to set it up")
    except Exception:
        logger.exception("Ignoring error during sending email")


def control_main(
    name: str,
    window_class: "type[ControlWindow]",
    guidicts: GuiDict | type[GuiDict] | Sequence[type[GuiDict] | GuiDict] | None = None,
    extra_cmds: dict | None = None,
    lockfile: bool = True,
    package: str = "matr1x",
    **kwargs: Any,
) -> None:
    """
    Run main function of control GUI.

    This function exists to avoid duplication in all control GUIs.

    Parameters
    ----------
    name : str
        Identifier string used as Window title and for the lock file.
    window_class : ControlWindow
        Class derived from QMainWindow to be used to construct the GUI.
    guidicts : GuiDict, list or tuple of GuiDicts, optional
        GuiDict class(es) with the definition of the GUI.
    extra_cmds : dict, optional
        Dictionary with commands for the measurement interface. While
        most commands will be connected with the GuiDicts, those which
        do not fit there can be supplied here.
    lockfile : bool, optional
        Boolean flag to specify if a lockfile shall be created/checked
        to avoid multiple instances of the control GUI. Default is True.
    package : str, optional
        Package name to identify the desktop file. Default is "matr1x".
    **kwargs : dict
        Keyword arguments which are forwarded to the window_class
        constructor.
    """
    if sys.platform == "win32":
        try:
            from ctypes import windll

            myappid = f"python.{package}.{name}.version"
            windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except ImportError:
            pass

    app = MApplication(sys.argv)
    install_error_handler()
    install_qt_error_dialog()
    app.setDesktopFileName(f"python.{package}.{Path(sys.argv[0]).name}")

    if lockfile:
        # lock files are stored in a user specific cache directory
        # to ensure they are available even if no log folder exists
        lockdir = Path(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
        )
        lockdir.mkdir(parents=True, exist_ok=True)
        lockfilename = lockdir / f"{package}_gui_{name}.lock"
        if lockfilename.exists():
            # check if process still running
            with lockfilename.open(encoding="utf-8") as lockf:
                otherpid = int(lockf.read())
            try:
                psutil.Process(otherpid)
                QMessageBox.critical(
                    QWidget(),
                    "Other instance running",
                    f"""Another instance of '{name}' was found running.
The control GUI can not start.
Kill the other process ({otherpid}) before restarting.""",
                )
                sys.exit()
            except psutil.NoSuchProcess:
                # this is the normal behavior in this case -> move on.
                pass
        # generate lockfile and write in the process ID
        with lockfilename.open("w", encoding="utf-8") as lockf:
            lockf.write(f"{os.getpid()}\n")

    kwargs["package"] = package
    logger.info("Starting GUI")
    ret = 1
    try:
        with window_class(name, guidicts=guidicts, extra_cmds=extra_cmds, **kwargs):
            ret = app.exec()
    except Exception as exc:
        logger.exception("Control GUI '%s' failed to start", name)
        QMessageBox.critical(
            None,
            "Control GUI startup failed",
            f"""The control GUI '{name}' could not be started.

{type(exc).__name__}: {exc}

See the application log for more details.""",
        )
    finally:
        if lockfile and lockfilename.exists():
            lockfilename.unlink()
    logger.info("Exiting GUI")
    sys.exit(ret)
