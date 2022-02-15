# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
import ast
import getpass
import logging
import os
import socket
import subprocess
import sys
import tempfile
import textwrap

import matr1x
from matr1x.control.util import QtGracefulKiller
from matr1x.util import generate_script
from PyQt5.QtCore import QRect, QRegExp, QSize, Qt, QThread
from PyQt5.QtGui import (QColor, QFont, QPainter, QPalette, QSyntaxHighlighter,
                         QTextCharFormat, QTextCursor)
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QFileDialog,
                             QGridLayout, QLineEdit, QListWidget,
                             QPlainTextEdit, QPushButton, QSplitter, QTextEdit,
                             QWidget)

from ..gui_util import EmittingStream

logger = logging.getLogger(os.path.split(__file__)[-1])
logger.info("matrix_script starting")


class LineNumberArea(QWidget):
    """
    adapted from the QT c++ example "Code Editor Example"
    """

    def __init__(self, editor):
        super().__init__(editor)
        self.codeeditor = editor

    def sizeHint(self):
        return QSize(self.editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeeditor.lineNumberAreaPaintEvent(event)


class CodeEditor(QPlainTextEdit):
    """
    adapted from the QT c++ example "Code Editor Example"
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)

        self.updateLineNumberAreaWidth(0)

    def lineNumberAreaWidth(self):
        digits = 1
        count = max(1, self.blockCount())
        while count >= 10:
            count /= 10
            digits += 1
        space = 4 + self.fontMetrics().width('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(),
                                       rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(
            QRect(cr.left(), cr.top(),
                  self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(
            self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and (top <= event.rect().bottom()):
            if block.isVisible() and (bottom >= event.rect().top()):
                number = str(blockNumber + 1)
                painter.setPen(Qt.black)
                painter.drawText(0, int(top), int(self.lineNumberArea.width()),
                                 int(self.fontMetrics().height()),
                                 Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1


# syntax highlighting taken from
# https://wiki.python.org/moin/PyQt/Python%20syntax%20highlighting
def format(color, style=''):
    """Return a QTextCharFormat with the given attributes.
    """
    _color = QColor()
    _color.setNamedColor(color)

    _format = QTextCharFormat()
    _format.setForeground(_color)
    if 'bold' in style:
        _format.setFontWeight(QFont.Bold)
    if 'italic' in style:
        _format.setFontItalic(True)

    return _format


# Syntax styles that can be shared by all languages
STYLES = {
    'keyword': format('blue'),
    'operator': format('red'),
    'brace': format('darkGray'),
    'defclass': format('black', 'bold'),
    'string': format('magenta'),
    'string2': format('darkMagenta'),
    'comment': format('darkGreen', 'italic'),
    'self': format('black', 'italic'),
    'numbers': format('brown'),
}


class PythonHighlighter(QSyntaxHighlighter):
    """
    Syntax highlighter for the Python language.
    """
    # Python keywords
    keywords = [
        'and', 'assert', 'break', 'class', 'continue', 'def',
        'del', 'elif', 'else', 'except', 'exec', 'finally',
        'for', 'from', 'global', 'if', 'import', 'in',
        'is', 'lambda', 'not', 'or', 'pass', 'print',
        'raise', 'return', 'try', 'while', 'yield',
        'None', 'True', 'False',
    ]

    # Python operators
    operators = [
        '=',
        # Comparison
        '==', '!=', '<', '<=', '>', '>=',
        # Arithmetic
        r'\+', '-', r'\*', '/', '//', r'\%', r'\*\*',
        # In-place
        r'\+=', '-=', r'\*=', '/=', r'\%=',
        # Bitwise
        r'\^', r'\|', r'\&', r'\~', '>>', '<<',
    ]

    # Python braces
    braces = [
        r'\{', r'\}', r'\(', r'\)', r'\[', r'\]',
    ]

    def __init__(self, document):
        super().__init__(document)

        # Multi-line strings (expression, flag, style)
        # FIXME: The triple-quotes in these two lines will mess up the
        # syntax highlighting from this point onward
        self.tri_single = (QRegExp("'''"), 1, STYLES['string2'])
        self.tri_double = (QRegExp('"""'), 2, STYLES['string2'])

        rules = []

        # Keyword, operator, and brace rules
        rules += [(r'\b%s\b' % w, 0, STYLES['keyword'])
                  for w in PythonHighlighter.keywords]
        rules += [(r'%s' % o, 0, STYLES['operator'])
                  for o in PythonHighlighter.operators]
        rules += [(r'%s' % b, 0, STYLES['brace'])
                  for b in PythonHighlighter.braces]

        # All other rules
        rules += [
            # 'self'
            (r'\bself\b', 0, STYLES['self']),

            # Double-quoted string, possibly containing escape sequences
            (r'"[^"\\]*(\\.[^"\\]*)*"', 0, STYLES['string']),
            # Single-quoted string, possibly containing escape sequences
            (r"'[^'\\]*(\\.[^'\\]*)*'", 0, STYLES['string']),

            # 'def' followed by an identifier
            (r'\bdef\b\s*(\w+)', 1, STYLES['defclass']),
            # 'class' followed by an identifier
            (r'\bclass\b\s*(\w+)', 1, STYLES['defclass']),

            # From '#' until a newline
            (r'#[^\n]*', 0, STYLES['comment']),

            # Numeric literals
            (r'\b[+-]?[0-9]+[lL]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b',
             0, STYLES['numbers']),
        ]

        # Build a QRegExp for each pattern
        self.rules = [(QRegExp(pat), index, fmt)
                      for (pat, index, fmt) in rules]

    def highlightBlock(self, text):
        """
        Apply syntax highlighting to the given block of text.
        """
        # Do other syntax formatting
        for expression, nth, format in self.rules:
            index = expression.indexIn(text, 0)

            while index >= 0:
                # We actually want the index of the nth match
                index = expression.pos(nth)
                length = len(expression.cap(nth))
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

        # Do multi-line strings
        in_multiline = self.match_multiline(text, *self.tri_single)
        if not in_multiline:
            in_multiline = self.match_multiline(text, *self.tri_double)

    def match_multiline(self, text, delimiter, in_state, style):
        """
        Do highlighting of multi-line strings. ``delimiter`` should be a
        ``QRegExp`` for triple-single-quotes or triple-double-quotes, and
        ``in_state`` should be a unique integer to represent the corresponding
        state changes when inside those strings. Returns True if we're still
        inside a multi-line string when this function is finished.
        """
        # If inside triple-single quotes, start at 0
        if self.previousBlockState() == in_state:
            start = 0
            add = 0
        # Otherwise, look for the delimiter on this line
        else:
            start = delimiter.indexIn(text)
            # Move past this match
            add = delimiter.matchedLength()

        # As long as there's a delimiter match on this line...
        while start >= 0:
            # Look for the ending delimiter
            end = delimiter.indexIn(text, start + add)
            # Ending delimiter on this line?
            if end >= add:
                length = end - start + add + delimiter.matchedLength()
                self.setCurrentBlockState(0)
            # No; multi-line string
            else:
                self.setCurrentBlockState(in_state)
                length = len(text) - start + add
            # Apply formatting
            self.setFormat(start, length, style)
            # Look for the next match
            start = delimiter.indexIn(text, start + length)

        # Return True if still inside a multi-line string, False otherwise
        if self.currentBlockState() == in_state:
            return True
        else:
            return False


class ExecThread(QThread):

    def __init__(self, sample, user, script, fallbackname):
        """
        initialize thread that handles script execution with meta data and
        script
        """
        super().__init__()
        self.proc = None
        self.conn = None
        self.sample = sample
        self.user = user
        self.script = script
        self.datafilefallback = fallbackname

    def pause(self):
        """ communicate pause to the subprocess' stdin """
        if self.proc is None or self.conn is None:
            return
        self.conn.send("p".encode())

    def stop(self):
        """ communicate stop to the subprocess' stdin """
        if self.proc is None or self.conn is None:
            return
        self.conn.send("q".encode())

    def abort(self):
        """ kill the process and make sure it is indeed stopped """
        if self.proc is None or self.conn is None:
            return
        pid = self.proc.pid
        # terminate thread
        self.proc.terminate()
        # if thread is still alive, kill it
        try:
            os.kill(pid, 0)
            self.proc.kill()
            print("force killed thread")
            print("please verify all devices are operational before starting",
                  "another script")
        except OSError:
            # this will likely not happen
            print("thread terminated gracefully")

    def run(self):
        """
        runs the subprocess
            first writes the user script into a temporary file to make sure all
            formating is conserved, then passes that file to the interpreter to
            run the script
            the purpose of using a subprocess is to keep the namespace clear of
            all system files. That allows changes to the system while
            matrix_script is running.
        """
        with tempfile.NamedTemporaryFile(mode="w+b") as tf:
            for line in self.script:
                tf.write(line.encode())
            # all information has been written to temporary file, make sure it
            # is updated
            tf.flush()
            # pass the script that we want to execute and generate correct
            # parameters to pass to matrix_script_process
            cmd = ("import matr1x.util as mu\n" +
                   f"mu.matrix_script_process({repr(tf.name)}, '" +
                   self.user + "', '" + self.sample + "', '" +
                   self.datafilefallback + "')")
            # start socket that is used to communicate with the child process
            # that runs the script
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # only accept local connections and start listening
            s.bind(('127.0.0.1', matr1x.scripts.MATRIX_SCRIPT_PORT))
            s.listen(1)
            # start subprocess, stderr is piped to stdout, and both of them are
            # piped so that we can read them
            self.proc = subprocess.Popen([sys.executable, "-c", cmd],
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT)
            # accept a connection from the subprocess
            # will block until a new client connects, might want to use select
            # here to make sure the subprocess actually connects?
            self.conn, address = s.accept()
            # wait until the subprocess terminates and pipe its stdout to the
            # user window
            while self.proc.poll() is None:
                print(self.proc.stdout.readline().decode())
            self.conn.close()


class MainWindow(QWidget):
    """
    Define layout, runs everything
    """

    def __init__(self):
        """
        Initialize the GUI for scripted matrix control
        """
        super().__init__()
        self.systems = []
        self.scriptname = ""

        self.init_ui()

        self.output_stream = EmittingStream(text_written=self.output_written)
        # set outputStream as stdout (i.e. all output is written to status
        # preview
        sys.stdout = self.output_stream

        welcome_string = textwrap.dedent(f"""
        Welcome {getpass.getuser()},
        available general functions are:
        ```
         init_datafile(filename, comment="", append=False, print_header=True)
         measure_system(print_data=True, print_telemetry=True)
         wait(seconds)
        ```
        `wait` also acts as breakpoint to pause execution.
        System parameters can be accessed via:
        ```
         set_value(value_index/name, value)
         trigger_value(value_index/name)
         read_value(value_index/name)
        ```
        Use the help button to get a list of available parameters and devices
        Devices can be accessed via the 'devs' dictionary. The meta data of
        the system is available through the 'meta_data' dictionary.

        Note that no variable names should start with an underscore!
        """)
        self.status_preview.setPlainText(welcome_string)
        print("==========")

    def init_ui(self):
        layout = QGridLayout()

        # Buttons
        self.start_button = QPushButton("Start recipe")
        self.start_button.clicked.connect(self.start_process)
        self.abort_button = QPushButton("Abort")
        self.abort_button.setEnabled(False)
        self.abort_button.clicked.connect(self.abort_thread)
        self.kill_button = QPushButton("Kill")
        self.kill_button.setEnabled(False)
        self.kill_button.clicked.connect(self.kill_thread)
        self.pause_button = QPushButton("Pause")
        self.pause_button.setCheckable(True)
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.pause_thread)
        self.save_button = QPushButton("Save recipe")
        self.save_button.clicked.connect(self.save_to_file)
        self.load_button = QPushButton("Load recipe")
        self.load_button.clicked.connect(self.load_from_file)
        self.help_button = QPushButton("Help")
        self.help_button.clicked.connect(self.show_commands)
        self.system_list = QListWidget()
        self.system_list.setSelectionMode(1)
        self.system_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.addButton = QPushButton('add system')
        self.addButton.clicked.connect(self.show_file_dialog)
        self.delButton = QPushButton('remove system')
        self.delButton.clicked.connect(self.delete_selected_system)

        # LineEdits
        self.sample_edit = QLineEdit(self)
        self.sample_edit.setPlaceholderText("sample name")
        self.user_edit = QLineEdit(self)
        self.user_edit.setPlaceholderText("user name")
        # TextEdits
        self.script_edit = CodeEditor(self)
        mono_font = QFont("Monospace")
        mono_font.setStyleHint(QFont.TypeWriter)
        self.script_edit.document().setDefaultFont(mono_font)
        self.highlighter = PythonHighlighter(self.script_edit.document())
        self.status_preview = QTextEdit(self)
        self.status_preview.setReadOnly(True)
        self.status_preview.setCurrentFont(mono_font)
        # self.status_preview.textChanged.connect(self.status_preview.setMarkdown)
        palette = self.status_preview.palette()
        palette.setColor(QPalette.Base, QColor(233, 233, 233))
        self.status_preview.setPalette(palette)

        # initialize widgets in layout
        splitter = QSplitter(self)
        splitter.addWidget(self.script_edit)
        splitter.addWidget(self.status_preview)
        layout.addWidget(splitter, 4, 0, 4, 8)
        layout.addWidget(self.sample_edit, 8, 0, 1, 4)
        layout.addWidget(self.user_edit, 8, 4, 1, 4)
        layout.addWidget(self.start_button, 9, 6, 1, 2)
        layout.addWidget(self.abort_button, 11, 6, 1, 2)
        layout.addWidget(self.kill_button, 12, 6, 1, 2)
        layout.addWidget(self.pause_button, 10, 6, 1, 2)
        layout.addWidget(self.save_button, 9, 0, 1, 2)
        layout.addWidget(self.load_button, 10, 0, 1, 2)
        layout.addWidget(self.help_button, 12, 0, 1, 2)
        layout.addWidget(self.system_list, 9, 2, 3, 4)
        layout.addWidget(self.addButton, 12, 2, 1, 2)
        layout.addWidget(self.delButton, 12, 4, 1, 2)

        # configure stretch to go only into textEdits
        layout.setRowStretch(4, 1)

        self.setLayout(layout)
        self.setWindowTitle('matrix_script')

    def show_file_dialog(self):
        """
        Opens a QFileDialog with filter system*.py
        """
        # get filenames from dialog
        filename = QFileDialog.getOpenFileName(
            self, 'Select system file', matr1x.systems_directory,
            "system files (system*.py)")[0]
        if "" == filename:
            return
        if os.path.dirname(filename) == matr1x.systems_directory:
            self.system_list.addItem(os.path.basename(filename))
        else:
            self.system_list.addItem(filename)

    def delete_selected_system(self):
        """
        Removes selected system from system_list. If no selection is active the
        last system will be removed.
        """
        selected = self.system_list.selectedItems()
        if len(selected) > 0:
            self.system_list.takeItem(self.system_list.row(selected[0]))
        elif 0 < self.system_list.count():
            self.system_list.takeItem(self.system_list.count()-1)

    def pause_thread(self):
        self.thread.pause()

    def abort_thread(self):
        self.thread.stop()

    def kill_thread(self):
        self.thread.abort()
        print("Script terminated by user - " +
              "file integrity might be compromised")

    def show_commands(self):
        """ prints information about current system to the status display """
        self.update_systems()
        if 0 == len(self.systems):
            print("No system selected")
            print("==========")
            return
        # use external process to not have the systems in the namespace
        info = subprocess.run([sys.executable, '-c',
                               "from matr1x import " +
                               "util;print(util" +
                               ".grab_system_information(" +
                               str(self.systems) + "))"],
                              capture_output=True)
        # print information string
        if info.returncode != 0:
            print("Error when trying to import system")
            print("----------")
            print((info.stderr).decode())
        else:
            print("Devices and commands for " + ", ".join(self.systems))
            print("----------")
            print((info.stdout).decode())
        print("==========")
        self.status_preview.moveCursor(QTextCursor.End)

    def output_written(self, text):
        """
        appends the most recent text to the end of the display and makes sure
        that the cursor remains at the end
        """
        if text.strip("\n") != "":
            self.status_preview.append(text.strip("\n"))
            self.status_preview.moveCursor(QTextCursor.End)

    def process_finished(self):
        """
        once the process is finished, return all buttons to original state and
        clean up thread
        """
        self.pause_button.setEnabled(False)
        self.pause_button.setChecked(False)
        self.abort_button.setEnabled(False)
        self.kill_button.setEnabled(False)
        self.script_edit.setReadOnly(False)
        self.start_button.setEnabled(True)
        self.addButton.setEnabled(True)
        self.delButton.setEnabled(True)
        print("Execution finished")
        print("==========")
        del self.thread

    def start_process(self):
        """
        disables/enables buttons to reflect the run state and extracts selected
        systems.
        Then runs the script defined in the edit
        """
        self.update_systems()
        if 0 == len(self.systems):
            print("No system selected")
            print("==========")
            return
        self.script_edit.setReadOnly(True)
        self.start_button.setEnabled(False)
        self.addButton.setEnabled(False)
        self.delButton.setEnabled(False)
        print("### Running script now")
        # define basic part of script, imports relevant commands
        user_script = self.script_edit.toPlainText()
        script = generate_script(self.systems, user_script)
        self.thread = ExecThread(self.sample_edit.text(),
                                 self.user_edit.text(),
                                 script,
                                 self.scriptname)
        self.thread.finished.connect(self.process_finished)
        logger.info("The following user script was run:\n" + user_script)
        self.thread.start()
        self.abort_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.kill_button.setEnabled(True)

    def update_systems(self):
        self.systems = [os.path.normpath(self.system_list.item(j).text())
                        for j in range(self.system_list.count())]
        systemnames = [os.path.split(os.path.splitext(sys)[0])[-1]
                       for sys in self.systems]

    def get_settable_info(self):
        """
        helper function to verify that the currents system and the one
        used for the loaded script match
        """
        try:
            settable_info = subprocess.run([sys.executable, '-c',
                                            "from matr1x import " +
                                            "util;print(util" +
                                            ".grab_system_information(" +
                                            str(self.systems) +
                                            ", settables=True))"],
                                           capture_output=True)
            return ast.literal_eval(settable_info.stdout.decode().split("\n")[-2])
        except Exception:
            return None

    def save_to_file(self):
        """
        saves the script to file, putting information about the system into
        the header
        """
        filename = QFileDialog.getSaveFileName(
            self, 'Specify Script',
            matr1x.usersfolder,
            "matrix files (*.matrix)")
        filename = filename[0]
        if "" == filename:
            print("Please specify file")
            print("==========")
            return
        elif ".matrix" not in filename:
            filename += ".matrix"
        try:
            output_file = open(filename, 'w')
        except (OSError, IOError):
            print("File cannot be opened")
            print("==========")
            return
        self.scriptname = filename
        self.update_systems()

        header = ""
        try:
            # get settable information to put into the header (columns/units)
            settable_info = self.get_settable_info()

            # write matrix file header
            header += "# system def : " + ",".join(self.systems) + "\n"
            header += "# system names : " + ",".join(settable_info[1]) + "\n"
            header += "# system units : " + ",".join(settable_info[2]) + "\n"
        except Exception:
            print("error in generating settable_info from file, telemetry "
                  "header could not be generated")
        script = self.script_edit.toPlainText()
        newscript = header
        for i, line in enumerate(script.split("\n")):
            if i < 3 and "# system " in line:
                # if there are already definitions of the system, skip them
                continue
            newscript += line + "\n"
        # set new script in editor and save it to the file
        self.script_edit.setPlainText(newscript)
        output_file.write(newscript)
        output_file.close()

    def load_from_file(self):
        """
        loads the script to file, making sure that header information specified
        still agree with the corresponding system
        """
        filename = QFileDialog.getOpenFileName(
            self, 'Select Script',
            matr1x.usersfolder,
            "matrix files (*.matrix)")
        filename = filename[0]
        if "" == filename:
            print("Please specify file")
            print("==========")
            return
        try:
            input_file = open(filename, 'r')
        except (OSError, IOError):
            print("File cannot be opened")
            print("==========")
            return
        self.scriptname = filename
        self.script_edit.clear()
        self.system_list.clear()
        settable_info = None
        sys_err = False
        for i, line in enumerate(input_file):
            if 0 == i:
                if "# system def : " in line:
                    # load system from definition in file
                    system_line = line.strip().replace(
                        "# system def : ", "")
                    for syst in system_line.split(","):
                        try:
                            self.system_list.addItem(syst)
                            self.update_systems()
                            settable_info = self.get_settable_info()
                        except KeyError:
                            sys_err = True
                            print("System that was used to generate the " +
                                  "script was not found in installed systems." +
                                  " Please check .matrix.conf file.")
                            print("==========\n")
                else:
                    print("No system defined in script, " +
                          "please choose system(s)")
                    print("==========\n")
            elif 1 == i and not sys_err:
                # make sure that system column definition agrees with
                # current system
                if "# system names : " in line and settable_info is not None:
                    system_names = line.strip().replace("# system names : ",
                                                        "")
                    if settable_info[1] != system_names.split(","):
                        print("Column names have changed between generation "
                              "of script and now, please make sure that "
                              "columns are set correctly before running the "
                              "script")
                        print("==========\n")
                else:
                    print("Could not verify column names, please verify"
                          " that columns have not changed")
                    print("==========\n")
            elif 2 == i and not sys_err:
                # make sure that system unit definition agrees with
                # current system
                if "# system units : " in line and settable_info is not None:
                    system_units = line.strip().replace("# system units : ",
                                                        "")
                    if settable_info[2] != system_units.split(","):
                        print("Column units have changed between generation "
                              "of script and now, please make sure that "
                              "columns are set correctly before running the "
                              "script")
                        print("==========\n")
                else:
                    print("Could not verify column units, please verify"
                          " that columns have not changed")
                    print("==========\n")
            self.script_edit.insertPlainText(line)
        input_file.close()


def main():
    app = QApplication(sys.argv)
    with QtGracefulKiller():
        ex = MainWindow()
        ex.show()
        ret = app.exec()
        sys.stdout = sys.__stdout__
    sys.exit(ret)
