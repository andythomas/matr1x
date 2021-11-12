import logging
import os
import sys
import threading
import time
import traceback
import types
from functools import wraps

from matr1x import datetimefmt, scpi_tcpserver
from PyQt5 import QtCore
from PyQt5.QtWidgets import QGridLayout, QMainWindow, QMessageBox, QWidget

logger = logging.getLogger(os.path.split(__file__)[-1])


def catchEmitError(method):
    """
    Define error handling decorator
    """
    @wraps(method)
    def decorated_method(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as exc:
            # end the refreshDict thread
            self.terminate = True
            if method.__name__ == 'refreshDict':
                # set terminated flag since our main loop is dead
                self.terminated = True
            # report error to the main thread
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.sig_error.emit(exc_type, exc_value, exc_traceback,
                                method.__name__)
            while True:
                # prevent prematurely cleaning up objects,
                # this otherwise causes a segmentation fault
                time.sleep(3)

    return decorated_method


class ControlWindow(QMainWindow):
    sig_error = QtCore.pyqtSignal(type, Exception, types.TracebackType, str)

    def __init__(self, name, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle(name)
        # initialize paramaters
        self.running = False
        self.terminate = False
        self.terminated = False
        self.devInit = False
        self.keep_enabled = []
        # initialize error handling
        self.sig_error.connect(self.handleError)
        # SCPI TCP server placeholders
        self.localServer = None
        self.cmd_list = []
        # initialize GUI
        self.initUI()
        self.show()

    # GUI functions
    def initUI(self):
        """
        Initializes GUI -> needs to overloaded/extended by any subclass
        """
        self.widget = QWidget()
        self.grid = QGridLayout()
        self.widget.setLayout(self.grid)
        self.setCentralWidget(self.widget)

    # device communication and related functions
    def connectDev(self):
        """
        init device connections -> needs to be implemented by every subclass and
        should set self.devInit to True once finished
        """
        raise NotImplementedError

    @catchEmitError
    def refreshDict(self):
        """
        This is the main loop updating the GUI fields!
        Here, the read out needs to be conducted thread safe.
        Needs to be implemented by every subclass.

        The main loop should terminate once self.terminate is set to True and
        set self.terminated once its successfully finished.

        Typically this class shall be decorated with the error handler to catch
        and terminate upon an uncaught Python exception.
        """
        raise NotImplementedError

    # general local server and start stop overhead
    def __enter__(self):
        """
        starts refreshing the values in a separate thread
        check also that the devices are initialized
        """
        # initialize devices
        print("initializing devices")
        self.connectDev()

        # initialize thread to refresh dicts
        # check if successful
        if self.devInit is True:
            self.t = threading.Thread(target=self.refreshDict, daemon=True)
            self.t.start()
            self.running = True
            self.startServer()

    def __exit__(self, exc_type, exc_value, traceback):
        """
        stops the refreshDict function and closes devices
        """
        if exc_type is not None:
            print(exc_type, exc_value, traceback)

        self.stopServer()
        if self.running is True:
            self.terminate = True
            self.runnnig = False
            # wait for refreshDict to terminate
            while self.terminated is False:
                time.sleep(0.01)

    def startServer(self):
        """
        starts the local TCP server with the driver functions specified
        in self.cmd_list
        """
        self.localServer = scpi_tcpserver.SCPI_TCP_Server(self.cmd_list)
        self.localServer.start()

    def stopServer(self):
        """
        stops the local TCP server
        """
        if self.localServer is not None:
            self.localServer.stop()
        self.localServer = None

    @QtCore.pyqtSlot(type, Exception, types.TracebackType, str)
    def handleError(self, exc_type, exc_value, exc_traceback, pointer):
        # disable all GUI elements but look at execption list
        for i in reversed(range(self.grid.count())):
            self.grid.itemAt(i).widget().setEnabled(False)
        for widget in self.keep_enabled:
            widget.setEnabled(True)
        # stop SCPI server to reflect that something is wrong instead of
        # returning the same reading over and over
        self.stopServer()
        # print timestamp and verbose error message to status display,
        # make a log entry and open a popup warning window
        timestamp = time.strftime(datetimefmt)
        print(timestamp)
        logger.info(f"handling error in {pointer}: {repr(exc_value)}")
        traceback.print_tb(exc_traceback)
        # duplicate to stdout
        traceback.print_tb(exc_traceback, file=sys.stdout)
        a = QMessageBox.critical(
            self, f"Error in {pointer}",
            f"""{timestamp}
The following error was raised in {pointer}:
{repr(exc_value)}
Please investigate the error and eventually restart the graphical user interface""")
