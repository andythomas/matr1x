# GUI frontend for the matrix program, offers preview capabilities and
# incorporates the self, sweepGenerator
#
# 2017/04/17 First version (pheowl)
# ---
import os
import signal
import socket
import subprocess
import sys
import time
from os.path import exists, getmtime, getsize

import matr1x
import pyqtgraph as pg
import pyqtgraph.exporters
from matr1x import gui_util as gu
from matr1x.control.util import QtGracefulKiller
from matr1x.eval import delta, get_latest_datafile, loadh5matrix, loadmatrix
from matr1x.scripts import MATRIX_GUI_PORT, sweep_generator
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QFileDialog, QGridLayout, QLabel, QLineEdit,
                             QPushButton, QTextEdit, QVBoxLayout, QWidget)


def signal_handler(signal, frame):
    # This takes care of any keyboard interrupt in the GUI
    return


# Connect keyboard interrupt with above signal handler
signal.signal(signal.SIGINT, signal_handler)


class updateThread(QThread):
    update_now = pyqtSignal()

    def __init__(self, interval):
        QThread.__init__(self)
        self.stopFlag = False
        self.interval = interval

    def run(self):
        while not self.stopFlag:
            time.sleep(self.interval)
            self.update_now.emit()

    def terminate(self):
        self.stopFlag = True


class SweepPreviewPopup(QDialog):
    """
    Popup showing the sweep as list and as plot

    Arguments:
        index -- index of column in sweep to be displayed on startup
        sweep -- list of sweeps for each column
        cols -- list of column names
        units -- list of column units
    """

    def __init__(self, parent, filename):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.filename = filename
        if ".h5" in filename:
            self.h5 = True
            self.header, self.data = loadh5matrix(self.filename)
        else:
            self.h5 = False
            self.header, self.data = loadmatrix(self.filename)
        self.udthread = None
        self.luTime = time.time()
        self.initUI()

    def initUI(self):
        """
        Initialize GUI for popup
        """
        grid = QGridLayout()

        closeButton = QPushButton("Close preview")
        closeButton.clicked.connect(self.close)

        updateButton = QPushButton("Update plot")
        updateButton.clicked.connect(self.refreshLists)

        saveButton = QPushButton("Save plot")
        saveButton.clicked.connect(self.savePlot)

        self.autoupdateBox = QCheckBox("Auto update data")
        auinit = False
        self.autoupdateBox.setChecked(auinit)
        self.autoupdateBox.toggled.connect(self.updatethread)
        self.updatethread(auinit)

        self.posLabel = QLabel("x: 0.0e-0\ny: 0.0e-0")
        fileLabel = QLabel(self.filename)
        self.setWindowTitle(os.path.basename(self.filename))

        self.textEdit = QTextEdit()
        self.textEdit.setReadOnly(True)
        self.textEdit.setMinimumHeight(100)

        comboBoxX = QComboBox()
        comboBoxY = QComboBox()
        self.comboBoxCalc = QComboBox()

        self.comboBoxCalc.addItems(["None", "Delta-", "Delta+"])
        self.dMode = 0

        comboBoxX.addItems(self.header[0])
        comboBoxY.addItems(self.header[0])
        self.indexX = 0
        self.indexY = 0
        comboBoxX.currentIndexChanged.connect(self.indexChangedX)
        comboBoxY.currentIndexChanged.connect(self.indexChangedY)

        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        self.vb = gu.CustomViewBox()
        self.pw = pg.PlotWidget(
            viewBox=self.vb, name="Plot1", enableMenu=False)
        self.plt = self.pw.plot()
        self.refreshLists()

        self.plotlineBox = QCheckBox("show plot line")
        lineinit = False
        self.plt.setPen(None)
        self.plotlineBox.setChecked(auinit)
        self.plotlineBox.toggled.connect(self.updatelinesetting)
        self.updatelinesetting(lineinit)

        self.proxy = pg.SignalProxy(self.pw.scene().sigMouseMoved,
                                    rateLimit=30,
                                    slot=self.mouseMoved)

        grid.addWidget(fileLabel, 11, 0, 1, -1)
        grid.addWidget(closeButton, 0, 0)
        grid.addWidget(updateButton, 4, 0)
        grid.addWidget(self.autoupdateBox, 5, 0)
        grid.addWidget(self.plotlineBox, 6, 0)
        grid.addWidget(comboBoxX, 1, 0)
        grid.addWidget(comboBoxY, 2, 0)
        grid.addWidget(self.comboBoxCalc, 3, 0)
        grid.addWidget(self.textEdit, 7, 0, 4, 1)
        grid.addWidget(saveButton, 0, 1, 1, 4)
        grid.addWidget(self.posLabel, 0, 5, 1, 1)
        grid.addWidget(self.pw, 1, 1, 10, 5)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(10, 1)

        self.setLayout(grid)
        self.show()

    def indexChangedX(self, newIndex):
        """
        If index is changed, show the interface for new index
        """
        self.indexX = newIndex
        self.plotList()
        self.updateTextEdit()

    def indexChangedY(self, newIndex):
        """
        If index is changed, show the interface for new index
        """
        self.indexY = newIndex
        self.plotList()
        self.updateTextEdit()

    def refreshLists(self):
        updated = self.openFileAndReadList()
        if self.dMode != self.comboBoxCalc.currentIndex() or updated is True:
            self.plotList()
            self.updateTextEdit()

    def mouseMoved(self, ev):
        mousePoint = self.vb.mapSceneToView(ev[0])
        self.posLabel.setText("x: {:e}\ny: {:e}".format(mousePoint.x(),
                                                        mousePoint.y()))

    def savePlot(self):
        exporter = pg.exporters.ImageExporter(self.vb.scene())
        filename = QFileDialog.getSaveFileName(
            self, 'Select output png file', matr1x.usersfolder,
            "png files (*.png)")[0]
        if ".png" != filename[-4:].lower():
            filename += ".png"
        exporter.export(filename)
        # exporter.parameters()["height"] = 1200
        # exporter.parameters()["width"] = 1920

    def updateTextEdit(self):
        """
        Updates the textEdit to show the current sweep[index]
        """
        self.textEdit.clear()
        if len(self.ydata) > 101:
            for index, item in zip(self.xdata[-100:], self.ydata[-100:]):
                self.textEdit.append("{:.5e} |{:.5e}".format(index, item))
        else:
            for index, item in zip(self.xdata, self.ydata):
                self.textEdit.append("{:.5e} |{:.5e}".format(index, item))

    def openFileAndReadList(self):
        if getsize(self.filename) > 300000 and time.time() - self.luTime < 20:
            # skip updates if delta is below 10s and filesize is > 200kB
            # this will depend on the system!
            return False
        if self.luTime < getmtime(self.filename):
            if self.h5 is True:
                self.header, self.data = loadh5matrix(self.filename)
            else:
                self.header, self.data = loadmatrix(self.filename)
            self.luTime = time.time()
            return True

    def updatethread(self, state):
        if state is True:
            # start updatethread with 2s refresh time
            self.udthread = updateThread(2)
            self.udthread.update_now.connect(self.refreshLists)
            self.udthread.start()
        if state is False and self.udthread is not None:
            self.udthread.terminate()
            self.udthread = None

    def updatelinesetting(self, state):
        if state is True:
            self.plt.setPen((0, 0, 153), width=3)
        if state is False:
            self.plt.setPen(None)

    def plotList(self):
        """
        Updates the plot to show sweep[index] against its range
        """
        self.dMode = self.comboBoxCalc.currentIndex()
        try:
            x = self.data[:, self.indexX]
            y = self.data[:, self.indexY]
        except IndexError:
            try:
                # if array can not be 2D sliced
                x = self.data[self.indexX]
                y = self.data[self.indexY]
                if len(x) != len(y):
                    # in case lengths do not agree, do not allow plotting
                    self.xdata = []
                    self.ydata = []
                    return
            except IndexError:
                # if array has length of 0
                self.xdata = []
                self.ydata = []
                return
            except TypeError:
                # only single point in file
                x = [self.data[self.indexX]]
                y = [self.data[self.indexY]]
        if 0 == self.dMode:
            self.xdata = x
            self.ydata = y
        elif 1 == self.dMode:
            self.xdata = delta(x)[0]
            self.ydata = delta(y)[1]
        elif 2 == self.dMode:
            self.xdata = delta(x)[0]
            self.ydata = delta(y)[0]
        """
        # if 3pt delta is wished for...
        elif 3 == self.dMode:
            self.xdata = delta3p(x)[0]
            self.ydata = delta3p(y)[1]
        elif 4 == self.dMode:
            self.xdata = delta3p(x)[0]
            self.ydata = delta3p(y)[0]
        """
        self.pw.getAxis("left").textWidth = 0
        self.plt.setData(y=self.ydata, x=self.xdata, symbol="o")
        self.pw.setLabel("bottom", self.header[0][self.indexX],
                         self.header[1][self.indexX])
        self.pw.setLabel("left", self.header[0][self.indexY],
                         self.header[1][self.indexY])


class ExecThread(QThread):
    filename_received = pyqtSignal(str)

    def __init__(self):
        QThread.__init__(self)

    def set_param(self, inputFile, outputFile, user, sample, comment):
        self.inputFile = inputFile
        self.outputFile = outputFile
        self.user = user
        self.sample = sample
        self.comment = comment

    def receive_filename(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', MATRIX_GUI_PORT))
        s.listen(1)
        conn, address = s.accept()  # will block until a new client connects

        # get filename which is sent by matrix
        data = ""
        while True:
            datachunk = conn.recv(1024)
            if not datachunk:
                break
            data += datachunk.decode()

        conn.close()
        self.filename_received.emit(data)

    def run(self):
        cmd = ["matrix", "-i", self.inputFile]
        if self.outputFile != "":
            cmd += ["-o", self.outputFile]
        for field, arg in ((self.user, "-u"),
                           (self.sample, "-S"),
                           (self.comment, "-m")):
            if field:
                cmd += [arg, field]
        print(subprocess.list2cmdline(cmd))
        ret = self.run_as_fg_process(cmd)
        print(f"matrix ended with returncode: {ret}")

    def run_as_fg_process(self, *args, **kwargs):
        """
        from https://stackoverflow.com/a/66727983/3504203
        On Windows a primitive fallback is used!

        the "correct" way of spawning a new subprocess:
        signals like C-c must only go
        to the child process, and not to this python.

        the args are the same as subprocess.Popen

        returns Popen().wait() value

        Some side-info about "how ctrl-c works":
        https://unix.stackexchange.com/a/149756/1321

        fun fact: this function took a whole night
                  to be figured out.
        """
        if os.name == 'nt':
            # fork the child
            child = subprocess.Popen(*args, **kwargs)
            # get filename back
            self.receive_filename()
            # wait for the child to terminate
            ret = child.wait()
        else:
            import termios

            old_pgrp = os.tcgetpgrp(sys.stdin.fileno())
            old_attr = termios.tcgetattr(sys.stdin.fileno())

            user_preexec_fn = kwargs.pop("preexec_fn", None)

            def new_pgid():
                if user_preexec_fn:
                    user_preexec_fn()

                # set a new process group id
                os.setpgid(os.getpid(), os.getpid())

                # generally, the child process should stop itself
                # before exec so the parent can set its new pgid.
                # (setting pgid has to be done before the child execs).
                # however, Python 'guarantee' that `preexec_fn`
                # is run before `Popen` returns.
                # this is because `Popen` waits for the closure of
                # the error relay pipe '`errpipe_write`',
                # which happens at child's exec.
                # this is also the reason the child can't stop itself
                # in Python's `Popen`, since the `Popen` call would never
                # terminate then.
                # `os.kill(os.getpid(), signal.SIGSTOP)`

            try:
                # fork the child
                child = subprocess.Popen(*args, preexec_fn=new_pgid,
                                         **kwargs)

                # we can't set the process group id from the parent since the
                # child will already have exec'd. and we can't SIGSTOP it before
                # exec, see above.
                # `os.setpgid(child.pid, child.pid)`

                # set the child's process group as new foreground
                os.tcsetpgrp(sys.stdin.fileno(), child.pid)
                # revive the child,
                # because it may have been stopped due to SIGTTOU or
                # SIGTTIN when it tried using stdout/stdin
                # after setpgid was called, and before we made it
                # forward process by tcsetpgrp.
                os.kill(child.pid, signal.SIGCONT)

                # get filename back
                self.receive_filename()

                # wait for the child to terminate
                ret = child.wait()

            finally:
                # we have to mask SIGTTOU because tcsetpgrp
                # raises SIGTTOU to all current background
                # process group members (i.e. us) when switching tty's pgrp
                # it we didn't do that, we'd get SIGSTOP'd
                # hdlr = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
                # signal library only works in the main thread
                # make us tty's foreground again
                os.tcsetpgrp(sys.stdin.fileno(), old_pgrp)
                # now restore the handler
                # signal.signal(signal.SIGTTOU, hdlr)
                # restore terminal attributes
                termios.tcsetattr(sys.stdin.fileno(),
                                  termios.TCSADRAIN, old_attr)

        return ret


class MainWindow(QWidget):
    """
    Define layout, runs everything
    """

    def __init__(self):
        super().__init__()
        self.initUI()
        self.sg = None
        self.thread = ExecThread()
        self.thread.filename_received.connect(self.outputEdit.setText)
        self.thread.finished.connect(self.processFinished)

    def closeEvent(self, event):
        if self.sg is not None:
            self.sg.close()
        event.accept()

    def initUI(self):
        """
        Initializes basic GUI matrix program
        """
        self.inputEdit = QLineEdit(self)

        inputButton = QPushButton("Select Input File")
        inputButton.clicked.connect(self.showInputDialog)

        sweepGenButton = QPushButton("Generate Sweep")
        sweepGenButton.clicked.connect(self.startSweepGenerator)

        self.outputEdit = QLineEdit(self)

        outputButton = QPushButton("Select Output File")
        outputButton.clicked.connect(self.showOutputDialog)

        self.userField = QLineEdit(self)
        self.userField.setToolTip("Measurement Operator for data-file header")
        self.sampleField = QLineEdit(self)
        self.sampleField.setToolTip("Sample identifier for data-file header")

        self.commentField = QTextEdit(self)
        self.commentField.setTabChangesFocus(True)
        self.commentField.setToolTip("Any measurement or sample information, \n"
                                     "which should be added to the data-file "
                                     "header")

        self.runButton = QPushButton("Enter Matrix")
        self.runButton.clicked.connect(self.runMatrix)

        self.previewButton = QPushButton("Preview Data")
        self.previewButton.clicked.connect(self.openPreview)

        fGrid = QGridLayout()
        fGrid.addWidget(sweepGenButton, 0, 0, 1, 11)

        fGrid.addWidget(QLabel("Input"), 1, 0)
        fGrid.addWidget(self.inputEdit, 1, 1, 1, 9)
        fGrid.addWidget(inputButton, 1, 10)

        fGrid.addWidget(QLabel("Output"), 2, 0)

        fGrid.addWidget(self.outputEdit, 2, 1, 1, 9)
        fGrid.addWidget(outputButton, 2, 10)

        fGrid.addWidget(QLabel("User"))
        fGrid.addWidget(self.userField, 3, 1, 1, 10)

        fGrid.addWidget(QLabel("Sample"))
        fGrid.addWidget(self.sampleField, 4, 1, 1, 10)

        fGrid.addWidget(QLabel("Comments"))
        fGrid.addWidget(self.commentField, 5, 1, 2, 10)

        fGrid.addWidget(self.runButton, 7, 0, 1, 11)
        fGrid.addWidget(self.previewButton, 8, 0, 1, 11)

        self.statusBar = QTextEdit(self)
        self.statusBar.setReadOnly(True)
        self.statusBar.setMinimumHeight(30)
        self.statusBar.setMaximumHeight(80)

        sGrid = QGridLayout()

        sGrid.addWidget(QLabel("Status"), 0, 0)
        sGrid.addWidget(self.statusBar, 0, 1, 1, 10)

        vBox = QVBoxLayout()
        vBox.addLayout(fGrid)
        vBox.addLayout(sGrid)

        self.setLayout(vBox)
        self.setWindowTitle('matrix_gui')

    def showInputDialog(self):
        """
        Opens a QFileDialog with filter for input files
        """
        folder = self.inputEdit.text()
        if "" == folder:
            folder = matr1x.usersfolder
        filename = QFileDialog.getOpenFileName(self, 'Select input file',
                                               folder,
                                               "input files (*.*t)")
        if "" != filename[0]:
            self.inputEdit.setText(filename[0])

    def showOutputDialog(self):
        """
        Opens a QFileDialog with filter for output files
        """
        folder = self.outputEdit.text()
        if "" == folder:
            folder = matr1x.usersfolder
        filename = QFileDialog.getSaveFileName(
            self, 'Select ma file', folder,
            "Output files (*.ma7);;Old output files (*.ma6)",
            options=QFileDialog.DontConfirmOverwrite)
        if "" != filename[0]:
            self.outputEdit.setText(filename[0])

    def startSweepGenerator(self):
        """
        Runs sweep Generator already initialized with system
        """
        if self.sg is None:
            self.sg = sweep_generator.MainWindow(inputcb=self.sGsetInputFile)
            self.sg.show()
        elif self.sg.isVisible() is False:
            self.sg.show()
        else:
            self.sg.raise_()

    def sGsetInputFile(self, filename):
        """
        Can be called externally for setting the input file
        """
        self.inputEdit.setText(filename)

    def runMatrix(self):
        """
        Runs the matrix program with the specified parameters
        """
        inputFile = self.inputEdit.text()
        outputFile = self.outputEdit.text()
        if "" == inputFile:
            self.statusBar.append("No input file specified")
            return
        self.runButton.setDisabled(True)
        self.thread.set_param(inputFile, outputFile,
                              self.userField.text(), self.sampleField.text(),
                              self.commentField.toPlainText())
        self.thread.start()

    def processFinished(self):
        self.runButton.setDisabled(False)

    def openPreview(self):
        output = self.outputEdit.text()
        if "" == output:  # try to obtain last filename from input file
            infile = self.inputEdit.text()
            if "" == infile:
                self.statusBar.append("Please specify a filename")
                return
            output = get_latest_datafile(basename=infile)
        if exists(output) is False:
            self.statusBar.append(f"File does not exist ({output})")
            return
        a = SweepPreviewPopup(self, output)
        a.show()


def main():
    app = QApplication(sys.argv)
    # we need to ignore this signal here otherwise we are kicked into
    # background when matrix returns. see run_as_fg_process
    if 'SIGTTOU' in dir(signal):  # signal only on POSIX compliant systems
        signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    with QtGracefulKiller():
        ex = MainWindow()
        ex.show()
        ret = app.exec()
    sys.exit(ret)
