# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
import logging
import os
import sys
import threading
import time
import traceback
import types
from functools import wraps

from matr1x import datetimefmt, logfolder, scpi_tcpserver, system
from matr1x.control.util import var
from matr1x.gui_util import EmittingStream
from matr1x.util import generate_datafilename, write_matrix_header

try:
    from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
    from PyQt6.QtGui import QColor, QIcon, QPalette, QTextCursor
    from PyQt6.QtWidgets import (QApplication, QCheckBox, QDockWidget,
                                 QFileDialog, QFrame, QGridLayout, QLabel,
                                 QMainWindow, QMessageBox, QPlainTextEdit,
                                 QPushButton, QScrollArea, QSizePolicy,
                                 QSpinBox, QToolButton, QVBoxLayout, QWidget)
except ImportError:
    from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
    from PyQt5.QtGui import QColor, QIcon, QPalette, QTextCursor
    from PyQt5.QtWidgets import (QApplication, QCheckBox, QDockWidget,
                                 QFileDialog, QFrame, QGridLayout, QLabel,
                                 QMainWindow, QMessageBox, QPlainTextEdit,
                                 QPushButton, QScrollArea, QSizePolicy,
                                 QSpinBox, QToolButton, QVBoxLayout, QWidget)

logger = logging.getLogger(os.path.split(__file__)[-1])


def catchEmitError(method):
    """
    Define error handling decorator
    """
    @wraps(method)
    def decorated_method(self, *args, **kwargs):
        try:
            method(self, *args, **kwargs)
        except Exception:
            # end the refreshDict thread
            self.terminate = True
            self.terminate_log = True
            if method.__name__ == 'refreshDict':
                # set terminated flag since our main loop is dead
                self.terminated = True
            elif method.__name__ == 'loggingFunc':
                self.terminated_log = True
            # report error to the main thread
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.sig_error.emit(exc_type, exc_value, exc_traceback,
                                method.__name__)
            # prevent prematurely cleaning up objects,
            # this otherwise causes (sometimes) a segmentation faultset_argon_setpoint
            time.sleep(0.05)

    return decorated_method


class CollapsibleBox(QWidget):
    # inspired from
    # https://github.com/MichaelVoelkel/qt-collapsible-section/blob/master/Section.py
    redraw_activity = pyqtSignal(bool)

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.toggle_button = QToolButton(self)
        self.header_line = QFrame(self)
        self.content_widget = QScrollArea(self)
        self.main_layout = QGridLayout(self)

        self.toggle_button.setStyleSheet("QToolButton {border: none;}")
        self.toggle_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)

        self.header_line.setFrameShape(QFrame.Shape.HLine)
        self.header_line.setFrameShadow(QFrame.Shadow.Sunken)
        self.header_line.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Maximum)

        self.content_widget.setSizePolicy(QSizePolicy.Policy.Expanding,
                                          QSizePolicy.Policy.Fixed)

        # start out collapsed
        self.content_widget.setMaximumHeight(0)
        self.content_widget.setMinimumHeight(0)

        self.main_layout.setVerticalSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        row = 0
        self.main_layout.addWidget(self.toggle_button, row, 0, 1, 1,
                                   Qt.AlignmentFlag.AlignLeft)
        self.main_layout.addWidget(self.header_line, row, 2, 1, 1)
        self.main_layout.addWidget(self.content_widget, row+1, 0, 1, 3)
        self.setLayout(self.main_layout)

        self.toggle_button.toggled.connect(self.toggle)

    def toggle(self, collapsed):
        if collapsed:
            self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
            self.content_widget.setMaximumHeight(self.content_height+1000)
            self.content_widget.setVisible(True)
            self.setMinimumHeight(self.collapsed_height)
            self.setMaximumHeight(self.combined_height+1000)
        else:
            self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
            self.content_widget.setMaximumHeight(0)
            self.setMinimumHeight(self.collapsed_height)
            self.setMaximumHeight(self.collapsed_height)
            self.content_widget.setVisible(False)
        self.updateGeometry()
        self.redraw_activity.emit(collapsed)

    def setContentLayout(self, layout):
        lay = self.content_widget.layout()
        del lay
        self.content_widget.setLayout(layout)
        self.content_height = self.content_widget.sizeHint().height()
        self.collapsed_height = self.sizeHint().height()  # - self.content_height
        self.combined_height = self.content_height + self.collapsed_height


class ControlWindow(QMainWindow):
    sig_error = pyqtSignal(type, Exception, types.TracebackType, str)
    activity = pyqtSignal(str)
    deactivate = pyqtSignal(bool)

    def __init__(self, name, guidicts=[], parent=None):
        # work around a bug in PyQt which can cause a segfault after a Python
        # exception. see issue #357
        os.environ["QT_NO_FT_CACHE"] = "1"

        super().__init__(parent=parent)
        self.setWindowTitle(name)
        # initialize paramaters
        self.running = False
        self.logging = False
        self.logfile = os.path.join(logfolder, name + ".ma7")
        self.terminate_log = False
        self.terminated_log = False
        self.terminate = False
        self.terminated = False
        self.devInit = False
        self.keep_enabled = []
        # initialize error handling
        self.sig_error.connect(self.handleError)
        # SCPI TCP server placeholders
        self.localServer = None
        # initialize data logging system
        self.S_log = system.System()
        self.S_log.__name__ = f"{name}_control_logging_system"
        # initialize data logging dictionaries
        self.guidicts = guidicts
        # harmonize the guidict data structure -> convert all to 'var'-objects
        for guidict in self.guidicts:
            for key in guidict:
                if not isinstance(guidict[key], var):
                    kwargs = dict()
                    if isinstance(guidict[key][0], var):
                        kwargs["dtype"] = (guidict[key][0].variableType,
                                           guidict[key][0].outType)
                        value = guidict[key][0].value
                    else:
                        kwargs["dtype"] = guidict[key][0]
                        value = None
                    if isinstance(guidict[key][1][-1], bool):
                        kwargs["columns"] = guidict[key][1][:-1]
                        kwargs["log"] = guidict[key][1][-1]
                    else:
                        kwargs["columns"] = guidict[key][1]
                    if len(guidict[key]) > 2:
                        kwargs["unit"] = guidict[key][2]
                    guidict[key] = var(**kwargs)
                    guidict[key]._value = value
        # initialize GUI
        self.initUI()
        # set outputStream as stdout (i.e. all output is written to status)
        self.output_stream = EmittingStream(text_written=self.output_written)
        sys.stdout = self.output_stream
        # show the GUI
        self.show()

    # GUI functions
    def initUI(self):
        """
        Initializes GUI -> needs to be extended by subclasses
        """
        layout = self.basicUI()
        self.guidictUI(layout)
        self.extra_layout(layout)
        self.statusloggingUI(layout)

    def basicUI(self):
        """Declare main GUI components and set Icon."""
        icondir = os.path.join(os.path.dirname(
            __file__), '..', 'scripts', 'icons')
        self.setWindowIcon(QIcon(os.path.join(icondir, 'matr1x-control.png')))
        self.widget = QWidget()
        self.widget.setSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Fixed)
        self.main_layout = QVBoxLayout()

        qApp = QApplication.instance()
        mainWindowBgColor = QPalette().color(QPalette.ColorRole.Window)
        qApp.setStyleSheet(
            f"[readOnly=\"true\"] {{background-color: {mainWindowBgColor.name(QColor.NameFormat.HexRgb)} }}")
        self.widget.setLayout(self.main_layout)
        self.setCentralWidget(self.widget)
        return self.main_layout

    def guidictUI(self, layout):
        """Setup guidict columns (main part of the ControlWindow)."""
        # construct the layout from the GUI dicts
        for guidict in self.guidicts:
            # create some frame and add it to the main layout
            content = QDockWidget(list(guidict.keys())[0])
            content.setFeatures(
                QDockWidget.DockWidgetFeature.DockWidgetMovable)
            container = QWidget()
            column = QVBoxLayout(container)
            content.setWidget(container)
            grid = QGridLayout()
            column.addLayout(grid)
            column.addStretch()
            self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, content)

            # fill it with the widgets from the variables
            for row, (key, variable) in enumerate(guidict.items()):
                variable.generate_widgets(key)

                for col, widget in enumerate(variable.widgets):
                    # add widgets to the grid layout at the correct position
                    # but skip hidden checkbox
                    if col == 0 and row == 0:
                        continue
                    grid.addWidget(widget, row, col, 1, 1)

    def extra_layout(self, layout):
        """Define extra fields needed for specific control GUIs"""

    def statusloggingUI(self, layout):
        """Setup status and logging user interface."""

        collapsible_box = CollapsibleBox("Logging and Status", parent=self)
        collapsible_box.redraw_activity.connect(self.readjustSize)
        self.status_grid = QGridLayout()
        layout.addWidget(collapsible_box)

        # initialize status_grid with common widgets
        self.status = QPlainTextEdit(self)
        self.status.setReadOnly(True)
        self.keep_enabled.append(self.status)
        self.activityIndicator = QLabel(" ")
        self.activityIndicator.setFixedWidth(40)
        self.activityIndicator.setFixedHeight(30)
        self.activityIndicator.setStyleSheet("background-color: lightgray")
        self.activity.connect(self.change_color)
        self.deactivate.connect(self.deactivate_gui)
        self.togglelog = QPushButton("start data log")
        self.togglelog.setCheckable(True)
        selectlog = QPushButton("select data log file")
        self.configlog = QPushButton("show logging config")
        self.configlog.setCheckable(True)
        self.loglabel = QLabel(os.path.basename(self.logfile))
        self.loglabel.setMaximumWidth(250)
        self.loglabel.setWordWrap(True)
        interval_label = QLabel("log interval (s):")
        self.interval = QSpinBox()
        self.interval.setRange(1, 24*3600+1)
        self.interval.setValue(60)
        self.interval.setMaximumWidth(70)
        self.togglelog.clicked.connect(self.toggleLog)
        selectlog.clicked.connect(self.selectLog)
        self.configlog.clicked.connect(self.configLog)

        # add status and logging widgets
        self.status_grid.addWidget(self.activityIndicator, 0, 0, 1, 1)
        self.status_grid.addWidget(interval_label, 0, 1, 1, 1)
        self.status_grid.addWidget(self.interval, 0, 2, 1, 1)
        self.status_grid.addWidget(self.configlog, 1, 0, 1, 3)
        self.status_grid.addWidget(self.togglelog, 2, 0, 1, 3)
        self.status_grid.addWidget(selectlog, 3, 0, 1, 3)
        self.status_grid.addWidget(self.loglabel, 4, 0, 2, 3)
        self.status_grid.addWidget(self.status, 0, 3, 7, 1)
        self.status_grid.setColumnStretch(3, 1)
        self.status_grid.setRowStretch(6, 1)

        collapsible_box.setContentLayout(self.status_grid)

    @staticmethod
    def copyValues(copyDict):
        """
        Copies the values of a guiDict (dictionary with var-instances) from the
        first to the second column.

        Parameters
        ------
        copyDict : dict
          guiDict for which the values shall be copied
        """
        for variable in copyDict.values():
            variable.copy_value()

    def output_written(self, text):
        """
        appends the most recent text to the end of the display and makes sure
        that the cursor remains at the end
        """
        if text.strip("\n") != "":
            self.status.appendPlainText(text.strip("\n"))
            try:
                self.status.moveCursor(QTextCursor.MoveOperation.End)
            except Exception:  # upon cleanup after exception this can fail
                pass

    @pyqtSlot(bool)
    def readjustSize(self, expanding=False):
        """
        resize window when the status and logging tab is minimized
        """
        if not expanding:
            # if we are shrinking the window and disabling the control, hide
            # the logging-config buttons
            self.configLog(False)
            self.configlog.setChecked(False)

        self.widget.adjustSize()
        self.adjustSize()

    # device communication and related functions
    def connectDev(self):
        """
        init device connections -> needs to be implemented by every subclass and
        should set self.devInit to True once finished
        """
        raise NotImplementedError

    def configLog(self, checked):
        for guidict in self.guidicts:
            for v in guidict.values():
                if len(v.widgets) > 2 and not isinstance(v.widgets[1], (QLabel, QPushButton)):
                    if isinstance(v.widgets[-1], QCheckBox):
                        v.widgets[-1].setVisible(checked)

    def toggleLog(self, checkstate):
        # clear system of all parameters
        self.S_log.clear_parameters()
        # add timestamp to system
        self.S_log.add_param("timeUTC", "s", getter=time.time)
        # set up system with selected values
        for i, guidict in enumerate(self.guidicts):
            for key in guidict:
                var = guidict[key]
                # make sure it is a loggable widget
                if len(var.widgets) > 2 and not isinstance(var.widgets[1], (QLabel, QPushButton)):
                    if bool(var.widgets[-1].checkState()):
                        # make sure check state is True and if so add to
                        # logged parameters
                        self.S_log.add_param(
                            f"dict{i}/{key}", "",
                            getter=lambda v=var: v.value)
        if len(self.S_log.parameters) == 1:
            print("No logging parameters were selected")
            return
        if self.logging is False:
            # generate new log filename
            self.logfile, mode = generate_datafilename(self.S_log,
                                                       outputfile=self.logfile)
            self.loglabel.setText(os.path.basename(self.logfile))
            # initialize system
            self.S_log.dcdata['Description'] = "Graphical interface logging data"
            self.S_log.dcdata['Type'] = "miscellaneous"
            self.S_log.set(output_file=self.logfile)
            # write new datafile header
            query_dict = self.S_log.query()
            write_matrix_header(
                self.logfile, mode, "matrix script generated",
                self.S_log, query_dict)
            # turn off config and set data
            self.configLog(False)
            self.configlog.setEnabled(False)
            self.configlog.setChecked(False)
            self.togglelog.setText("data log running")
            # start thread
            self.terminate_log = False
            self.terminated_log = False
            self.tlog = threading.Thread(target=self.loggingFunc,
                                         daemon=True)
            self.tlog.start()
            self.logging = True
            print("data logging started")

        elif self.logging is True:
            self.S_log.reset()
            self.terminate_log = True
            self.logging = False
            # reset GUI
            self.configlog.setEnabled(True)
            self.togglelog.setText("start data log")
            print("data logging stopped")

    def selectLog(self, *args):
        # allow selecting a logfile
        filename = QFileDialog.getSaveFileName(
            self, "Select log file", logfolder,
            "data log files (*.ma7)")[0]
        self.logfile = filename or self.logfile
        if "ma7" not in self.logfile:
            self.logfile += ".ma7"
        self.loglabel.setText(os.path.basename(self.logfile))

    @catchEmitError
    def loggingFunc(self):
        cnt = 0
        while not self.terminate_log:
            # get interval and initialize counter for seconds
            interval = self.interval.value()
            if 0 == cnt:
                # every interval seconds, perform log
                self.S_log.trigger()
                self.S_log.take_measurement_point(self.logfile)
            # ensure logging is interruptible even while waiting for
            # the next logpoint
            cnt = (cnt+1) % interval
            time.sleep(1)
        self.terminated_log = True

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
            self.running = False
            # wait for refreshDict to terminate
            while self.terminated is False:
                time.sleep(0.01)
        if self.logging is True:
            self.terminate_log = True
            self.logging = False
            # wait for logging to terminate
            while self.terminated_log is False:
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

    @pyqtSlot(str)
    def change_color(self, color):
        self.activityIndicator.setStyleSheet(f"background-color: {color}")

    @pyqtSlot(bool)
    def deactivate_gui(self, flag):
        """disable all GUI elements.

        This is typically emitted after an error.
        """
        if flag:
            # disable all GUI elements but look at execption list
            for g in self.guidicts:
                for v in g.values():
                    for widget in v.widgets[1:]:
                        widget.setEnabled(False)
            for i in reversed(range(self.status_grid.count())):
                self.status_grid.itemAt(i).widget().setEnabled(False)
            for widget in self.keep_enabled:
                widget.setEnabled(True)

    @pyqtSlot(type, Exception, types.TracebackType, str)
    def handleError(self, exc_type, exc_value, exc_traceback, pointer):
        self.activity.emit("lightgray")
        self.deactivate.emit(True)
        qApp = QApplication.instance()
        qApp.processEvents()
        # stop SCPI server to reflect that something is wrong instead of
        # returning the same reading over and over
        self.stopServer()
        # print timestamp and verbose error message to status display,
        # make a log entry and open a popup warning window
        timestamp = time.strftime(datetimefmt)
        print(timestamp)
        logger.info("handling error in %s: %s", pointer, repr(exc_value))
        traceback.print_tb(exc_traceback)
        # duplicate to stdout
        traceback.print_tb(exc_traceback, file=sys.stdout)
        a = QMessageBox.critical(
            self, f"Error in {pointer}",
            f"""{timestamp}
The following error was raised in {pointer}:
{repr(exc_value)}
Please investigate the error and eventually restart the graphical user interface""")
        ret = qApp.exec()
        if ret != -1:
            sys.exit(ret+1)
