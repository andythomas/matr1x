# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
import os
import signal
import socket
import subprocess
import sys
from os.path import dirname, exists, join

import matr1x
from matr1x.control.util import QtGracefulKiller
from matr1x.eval import get_latest_datafile
from matr1x.scripts import MATRIX_GUI_PORT, matrix_preview, sweep_generator
from matr1x.util import get_matrix_binary
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QApplication, QCheckBox, QFileDialog, QGridLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit,
                             QVBoxLayout, QWidget)


def signal_handler(signal, frame):
    # This takes care of any keyboard interrupt in the GUI
    return


# Connect keyboard interrupt with above signal handler
signal.signal(signal.SIGINT, signal_handler)

if os.name == 'nt':
    try:
        from ctypes import windll  # Only exists on Windows.
        myappid = 'python.matr1x.matrix_gui.version'
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


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
        cmd = [get_matrix_binary(), "-i", self.inputFile]
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
        basedir = dirname(__file__)
        self.setWindowIcon(QIcon(join(basedir, 'matr1x-matrix_gui.png')))
        self.inputEdit = QLineEdit(self)

        inputButton = QPushButton("Select Input File")
        inputButton.clicked.connect(self.showInputDialog)

        sweepGenButton = QPushButton("Generate Sweep")
        sweepGenButton.clicked.connect(self.startSweepGenerator)

        self.outputEdit = QLineEdit(self)
        self.outputAutoGen = QCheckBox(self)
        autogen = True
        self.outputAutoGen.setChecked(autogen)

        self.outputButton = QPushButton("Select Output File")
        self.outputButton.clicked.connect(self.showOutputDialog)
        self.outputAutoGen.toggled.connect(self.updateAutoGenFilename)
        self.updateAutoGenFilename(autogen)

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
        fGrid.addWidget(QLabel("auto-generate filename"), 2, 1)
        fGrid.addWidget(self.outputAutoGen, 2, 2)

        fGrid.addWidget(self.outputEdit, 3, 1, 1, 9)
        fGrid.addWidget(self.outputButton, 3, 10)

        fGrid.addWidget(QLabel("User"))
        fGrid.addWidget(self.userField, 4, 1, 1, 10)

        fGrid.addWidget(QLabel("Sample"))
        fGrid.addWidget(self.sampleField, 5, 1, 1, 10)

        fGrid.addWidget(QLabel("Comments"))
        fGrid.addWidget(self.commentField, 6, 1, 2, 10)

        fGrid.addWidget(self.runButton, 8, 0, 1, 11)
        fGrid.addWidget(self.previewButton, 9, 0, 1, 11)

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

    def updateAutoGenFilename(self, state):
        if state is True:
            # disable output filename fields
            self.outputEdit.setEnabled(False)
            self.outputButton.setEnabled(False)
        if state is False:
            self.outputEdit.setEnabled(True)
            self.outputButton.setEnabled(True)

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
        if self.outputAutoGen.isChecked():
            outputFile = ""
        else:
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
        a = matrix_preview.SweepPreview(self, output)
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
