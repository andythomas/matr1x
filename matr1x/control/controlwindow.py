# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2023 matr1x developers. All rights reserved.
# ---
import ast
import logging
import os
import pickle
import sys
import threading
import time
import warnings

from matr1x import logfolder, scpi_tcpserver, system
from matr1x.control.util import GuiDict, catchEmitError, var
from matr1x.gui_util import EmittingStream
from matr1x.util import Get, generate_datafilename, write_matrix_header

try:
    from PyQt6.QtCore import QSettings, Qt, pyqtSignal, pyqtSlot
    from PyQt6.QtGui import (QColor, QIcon, QKeySequence, QPalette, QShortcut,
                             QTextCursor)
    from PyQt6.QtWidgets import (QApplication, QCheckBox, QDockWidget,
                                 QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                                 QLabel, QMainWindow, QMessageBox,
                                 QPlainTextEdit, QPushButton, QScrollArea,
                                 QSizePolicy, QSpinBox, QToolButton,
                                 QVBoxLayout, QWidget)
except ImportError:
    from PyQt5.QtCore import QSettings, Qt, pyqtSignal, pyqtSlot
    from PyQt5.QtGui import QColor, QIcon, QKeySequence, QPalette, QTextCursor
    from PyQt5.QtWidgets import (QApplication, QCheckBox, QDockWidget,
                                 QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                                 QLabel, QMainWindow, QMessageBox,
                                 QPlainTextEdit, QPushButton, QScrollArea,
                                 QShortcut, QSizePolicy, QSpinBox, QToolButton,
                                 QVBoxLayout, QWidget)

logger = logging.getLogger(os.path.split(__file__)[-1])


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
    """
    Base class for control GUIs which prepares a lot of things behind the
    scences for use in typical control GUIs

    Parameters
    ----------
    name: str
      Identifier string of the control GUI
    guidicts: list, tuple of GuiDict
      Several GuiDict objects which build the basis of the controlGUI
    extra_cmds: dict, optional
      Dictionary of commands offered for the measurement system. Commands from
      the GuiDict object are merged together with this list.
    """
    sig_error = pyqtSignal(type, Exception, str)
    activity = pyqtSignal(str)
    deactivate = pyqtSignal(bool)

    def __init__(self, name, guidicts=None, extra_cmds=None, parent=None):
        # work around a bug in PyQt which can cause a segfault after a Python
        # exception. see issue #357
        os.environ["QT_NO_FT_CACHE"] = "1"

        super().__init__(parent=parent)
        self.setWindowTitle(name)
        self.settings = QSettings("matr1x", name)
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
        self._local_server = None
        # initialize data logging system
        self.S_log = system.System()
        self.S_log.__name__ = f"{name}_control_logging_system"
        # initialize data logging dictionaries
        if guidicts:
            self.guidicts = list(guidicts)
        else:
            self.guidicts = []
        # harmonize guidict entries to 'var'-objects
        for guidict in self.guidicts:
            for key, entry in guidict.items():
                if not isinstance(entry, var):
                    kwargs = {}
                    if isinstance(entry[0], var):
                        kwargs["dtype"] = (guidict[key][0].variableType,
                                           guidict[key][0].outType)
                        value = entry[0].value
                    else:
                        kwargs["dtype"] = entry[0]
                        value = None
                    if isinstance(entry[1][-1], bool):
                        kwargs["columns"] = entry[1][:-1]
                        kwargs["log"] = entry[1][-1]
                    else:
                        kwargs["columns"] = entry[1]
                    if len(entry) > 2:
                        kwargs["unit"] = entry[2]
                    guidict[key] = var(**kwargs)
                    guidict[key]._value = value
        # harmonize the guidict data structure -> convert all to GuiDict
        for i, guidict in enumerate(self.guidicts):
            if not isinstance(guidict, GuiDict):
                warnings.warn(
                    "Consider rewriting the GUI using the GuiDict class.",
                    FutureWarning)

                class _FakeGuiDict(GuiDict):
                    data = guidict

                    def refresh(self, *args):
                        pass

                self.guidicts[i] = _FakeGuiDict()
        for guidict in self.guidicts:
            guidict.refresh_worker.sig_error.connect(self.handleError)
        # set parent reference on guidicts
        for g in self.guidicts:
            g.parent = self
        # initialize GUI
        self.initUI()
        # restore settings of GuiDicts
        for g in self.guidicts:
            g.dock.restoreState()
            g.enable_switch.setChecked(not g.dock.disabled)
            g.restoreFeatures()
        # restore geometry settings of main window
        if self.settings.value("size") is not None:
            self.resize(self.settings.value("size"))
        if self.settings.value("pos") is not None:
            self.move(self.settings.value("pos"))
        if self.settings.value("windowState") is not None:
            self.restoreState(self.settings.value("windowState"))

        # enable saving of geometry by Ctrl+S
        self.saveStateSc = QShortcut(QKeySequence('Ctrl+S'), self)
        self.saveStateSc.activated.connect(self.saveCurrentState)
        for g in self.guidicts:
            self.saveStateSc.activated.connect(g.dock.saveCurrentState)
        # set outputStream as stdout (i.e. all output is written to status)
        self.output_stream = EmittingStream(text_written=self.output_written)
        sys.stdout = self.output_stream

        # merge the guidicts Systems
        if not hasattr(self, "S"):
            self.S = system.MergedSystem([g.S for g in self.guidicts])
        # store commands
        self.cmd_list = {":conf": Get(
            lambda b: pickle.loads(ast.literal_eval(b)).decode(),
            lambda: pickle.dumps(self.S.query(), protocol=0)
        )}
        if extra_cmds:
            self.cmd_list.update(extra_cmds)
        # show the GUI
        self.show()

        # connect signals so that at least one dock remains visible! (needs to be done after show!)
        for g in self.guidicts:
            g.dock.dockLocationChanged.connect(self.check_dock_status)
            g.dock.visibilityChanged.connect(self.check_dock_status)
            g.dock.dockClosed.connect(self.check_dock_status)

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
        """Setup guidict columns (main part of the ControlWindow).

        Parameters
        ----------
        layout : Qt-layout of main window.
        """
        # construct the layout from the GUI dicts
        #self._dockwidgets = []
        for guidict in self.guidicts:
            content = guidict.create_GUI()
            self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, content)
            #self._dockwidgets.append(content)

    @pyqtSlot()
    def check_dock_status(self):
        """
        In case of undocking/redocking check that at least one dockwidget
        remains docked and eventually disable the undocking feature!
        """
        # count docked widgets
        count_docked = sum(int(not g.dock.isFloating())
                           for g in self.guidicts)
        # count visible widgets
        count_vis = sum(int(g.dock.isVisible()) for g in self.guidicts)
        if count_docked <= 1 or count_vis <= 1:
            # forbid last visible/docked widget to be undocked
            for g in self.guidicts:
                dock = g.dock
                if not dock.isFloating():
                    dock.setFeatures(
                        dock.features() &
                        ~QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        else:
            for g in self.guidicts:
                dock = g.dock
                dock.setFeatures(
                    dock.features() |
                    QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        if count_vis <= 1:
            # redock last visible widget
            for g in self.guidicts:
                dock = g.dock
                if dock.isWindow() and dock.isVisible():
                    dock.setFloating(False)
                    break

    def extra_layout(self, layout):
        """
        Define extra fields needed for specific control GUIs.

        By default a central panic buttton is privided which will signal to all
        GUI elements to be put into a save state.
        """
        elayout = QHBoxLayout()
        self.panicButton = QPushButton("Panic Button")
        self.panicButton.setStyleSheet("background-color: red;")
        self.panicButton.setCheckable(True)
        elayout.addWidget(self.panicButton)
        self.panicButton.clicked.connect(self.panic)
        layout.insertLayout(0, elayout)

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
        self.activityIndicator = []
        activity_layout = QHBoxLayout()
        activity_layout.setSpacing(0)
        for idx, guidict in enumerate(self.guidicts):
            ql = QLabel(" ")
            ql.setFixedWidth(int(40/len(self.guidicts)))
            ql.setFixedHeight(30)
            ql.setStyleSheet("background-color: lightgray")
            self.activityIndicator.append(ql)
            guidict.refresh_worker.activity.connect(
                lambda c, idx=idx: self.change_single_color(c, idx))
            activity_layout.addWidget(ql)

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
        self.status_grid.addLayout(activity_layout, 0, 0, 1, 1)
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

        This method is deprecated. It is now part of GuiDict. Its use should
        vanish in the future.
        """
        warnings.warn(
            "copyValues is deprecated. Consider using GuiDict.copy_values.",
            FutureWarning)
        for variable in copyDict.values():
            variable.copy_value()

    @catchEmitError
    def panic(self, checked):
        """
        Panic button was pressed. Signal panic mode to guidicts if the button is
        checked.
        """
        if checked:
            for g in self.guidicts:
                g.panic()
        else:
            for g in self.guidicts:
                g.unpanic()

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
    @catchEmitError
    def connectDev(self):
        """
        init device connections

        If this is overloaded its important that the self.devInit property is
        set to True upon successful initialization of the devices.
        """
        if self.devInit is False:
            if self.S:
                self.S.set()
            self.devInit = True

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
        # start guidicts and get minimum period
        refresh_period = 0.1
        for guidict in self.guidicts:
            dockw = guidict.dock
            if not dockw.isVisible():
                guidict.enable_switch.setChecked(False)
                guidict.restoreFeatures()
            else:
                guidict.start()
            refresh_period = min(refresh_period, guidict.refresh_period)
        while True:
            time.sleep(refresh_period)
            if self.terminate:
                for guidict in self.guidicts:
                    if guidict.running:
                        guidict.stop()
                break

        # flag for stating that thread has ended
        self.terminated = True

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
            # merge all cmds from the GuiDicts and the extra cmds

            class extraGuiDict(GuiDict):
                cmds = self.cmd_list

                def refresh(self, *args):
                    pass

            extra_gui_dict = extraGuiDict()
            extra_gui_dict.set_cmd_funcs(window_obj=self, sys=self.S)
            self.cmd_list = extra_gui_dict.cmds
            for guidict in self.guidicts:
                # convert function names to executables
                guidict.set_cmd_funcs(window_obj=self, sys=self.S)
                for name, cmd in guidict.cmds.items():
                    if name in self.cmd_list:
                        raise ValueError(
                            f"command {name} from {guidict} is already present."
                            "A command name must be unique!")
                    self.cmd_list[name] = cmd

            self.t = threading.Thread(target=self.refreshDict, daemon=True)
            self.t.start()
            self.running = True
            self.startServer()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """
        stops the refreshDict function and closes devices
        """
        if exc_type is not None:
            print(exc_type, exc_value, exc_traceback)

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
        in cmds
        """
        self._local_server = scpi_tcpserver.SCPI_TCP_Server(self.cmd_list)
        self._local_server.start()

    def stopServer(self):
        """
        stops the local TCP server
        """
        if self._local_server is not None:
            self._local_server.stop()
        self._local_server = None

    def change_single_color(self, color, idx):
        self.activityIndicator[idx].setStyleSheet(f"background-color: {color}")

    @pyqtSlot(str)
    def change_color(self, color):
        for ql in self.activityIndicator:
            ql.setStyleSheet(f"background-color: {color}")

    @pyqtSlot(bool)
    def deactivate_gui(self, flag):
        """disable all GUI elements.

        This is typically emitted after an error.
        """
        if flag:
            # disable all GUI elements but look at execption list
            for g in self.guidicts:
                # disable all GUI elements but look at execption list
                g.dock.setEnabled(False)
                # GuiDict disable themselves, but repeat it here for backward
                # compatibility
                for v in g.values():
                    for widget in v.widgets:
                        widget.setEnabled(False)
            for i in reversed(range(self.status_grid.count())):
                w = self.status_grid.itemAt(i).widget()
                if w:
                    w.setEnabled(False)
            for widget in self.keep_enabled:
                widget.setEnabled(True)

    @pyqtSlot()
    def saveCurrentState(self):
        """
        Save current window and dock geometry which will be reloaded upon
        restart of the Control GUI.
        If this should be done on every close this method should be called
        from the closeEvent.
        """
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("windowState", self.saveState())

    @pyqtSlot(type, Exception, str)
    def handleError(self, exc_type, exc_value, pointer):
        """
        Signal slot to handle showing the error message and disabling the GUI
        """
        # end the refreshDict thread
        self.terminate = True
        self.terminate_log = True
        # stop guidicts immediately on error (Prevents a sometimes occuring
        # timeout error)
        for guidict in self.guidicts:
            if guidict.running:
                guidict.stop(wait=False)
        if pointer == 'refreshDict':
            # set terminated flag since our main loop is dead
            self.terminated = True
        elif pointer == 'loggingFunc':
            self.terminated_log = True
        self.activity.emit("lightgray")
        self.deactivate.emit(True)
        qApp = QApplication.instance()
        qApp.processEvents()
        # stop SCPI server to reflect that something is wrong instead of
        # returning the same reading over and over
        self.stopServer()
        # open a popup window to inform about the error
        a = QMessageBox.critical(
            self, f"Error in {pointer}",
            f"""The following error was raised in {pointer}:
{repr(exc_value)}
Please investigate the error and eventually restart the graphical user interface""")
        ret = qApp.exec()
        if ret != -1:
            sys.exit(ret+1)
