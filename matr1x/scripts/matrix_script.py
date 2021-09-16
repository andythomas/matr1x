# matrix Script GUI
#
# 2018/07/03 First version (pheowl)
# ---

import ast
import getpass
import logging
import os
import subprocess
import sys
import tempfile

from matr1x import systems_directory
from matr1x.control.util import QtGracefulKiller
from matr1x.util import generate_script
from PyQt5.QtCore import QRegExp, QThread
from PyQt5.QtGui import (QColor, QFont, QPalette, QSyntaxHighlighter,
                         QTextCharFormat, QTextCursor)
from PyQt5.QtWidgets import (QApplication, QFileDialog, QGridLayout, QLineEdit,
                             QListWidget, QPlainTextEdit, QPushButton,
                             QTextEdit, QWidget)

from ..gui_util import EmittingStream

logger = logging.getLogger(os.path.split(__file__)[-1])
logger.info("matrix_script starting")


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


class PythonHighlighter (QSyntaxHighlighter):
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

    def __init__(self, sample, user, script):
        """
        initialize thread that handles script execution with meta data and
        script
        """
        super().__init__()
        self.proc = None
        self.sample = sample
        self.user = user
        self.script = script

    def pause(self):
        """ communicate pause to the subprocess' stdin """
        if self.proc is None:
            return
        self.proc.stdin.write("p\n".encode())
        self.proc.stdin.flush()

    def stop(self):
        """ communicate stop to the subprocess' stdin """
        if self.proc is None:
            return
        self.proc.stdin.write("q\n".encode())
        self.proc.stdin.flush()

    def abort(self):
        """ kill the process and make sure it is indeed stopped """
        if self.proc is None:
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
                   self.user + "', '" + self.sample + "')")
            # start subprocess, stderr is piped to stdout, and both of them are
            # piped so that we can read/write to them
            self.proc = subprocess.Popen([sys.executable, "-c", cmd],
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT)
            # wait until the subprocess terminates and pipe its stdout to the
            # user window
            while self.proc.poll() is None:
                print(self.proc.stdout.readline().decode())


class MainWindow(QWidget):
    """
    Define layout, runs everything
    """

    def __init__(self):
        """
        Initialize the GUI for scripted matrix control
        """
        super().__init__()
        self.system_dict = {}
        index = 0
        for syst in os.listdir(systems_directory):
            if "system_" in syst:
                self.system_dict[syst.replace(".py", "")] = index
                index += 1

        self.systems = []

        self.init_ui()

        self.output_stream = EmittingStream(text_written=self.output_written)
        # set outputStream as stdout (i.e. all output is written to status
        # preview
        sys.stdout = self.output_stream

        welcome_string = f"Welcome {getpass.getuser()},\n"
        welcome_string += "available general functions are:\n"
        welcome_string += "```\n"
        # welcome_string += " trigger_system()\n"
        welcome_string += " measure_system(filename, comment='')\n"
        welcome_string += " wait(seconds)\n"
        welcome_string += "```\n"
        welcome_string += "`wait` also acts as breakpoint to pause execution.\n"
        welcome_string += "System parameters can be accessed via:\n"
        welcome_string += "```\n"
        welcome_string += " set_value(value_index, value)\n"
        # welcome_string += " trigger_value(value_index)\n"
        welcome_string += " read_value(value_index)\n"
        welcome_string += "```\n"
        welcome_string += "Use the help button to get a list "
        welcome_string += "of available parameters and devices.\n"
        welcome_string += "Devices can be accessed "
        welcome_string += "via the 'devs' dictionary.\n"
        self.status_preview.setMarkdown(welcome_string)
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
        self.system_list.insertItems(0, self.system_dict.keys())
        self.system_list.setSelectionMode(2)

        # LineEdits
        self.sample_edit = QLineEdit(self)
        self.sample_edit.setPlaceholderText("sample name")
        self.user_edit = QLineEdit(self)
        self.user_edit.setPlaceholderText("user name")
        # TextEdits
        self.script_edit = QPlainTextEdit(self)
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
        layout.addWidget(self.script_edit, 4, 0, 4, 4)
        layout.addWidget(self.status_preview, 4, 4, 4, 4)
        layout.addWidget(self.sample_edit, 8, 0, 1, 4)
        layout.addWidget(self.user_edit, 8, 4, 1, 4)
        layout.addWidget(self.start_button, 9, 6, 1, 2)
        layout.addWidget(self.abort_button, 11, 6, 1, 2)
        layout.addWidget(self.kill_button, 12, 6, 1, 2)
        layout.addWidget(self.pause_button, 10, 6, 1, 2)
        layout.addWidget(self.save_button, 9, 0, 1, 2)
        layout.addWidget(self.load_button, 10, 0, 1, 2)
        layout.addWidget(self.help_button, 12, 0, 1, 2)
        layout.addWidget(self.system_list, 9, 2, 4, 4)

        # configure stretch to go only into textEdits
        layout.setRowStretch(4, 1)

        self.setLayout(layout)
        self.setWindowTitle('matrix_script')

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
        print("Devices and commands for " + ", ".join(self.systems))
        print("----------")
        # use external process to not have the systems in the namespace
        info = subprocess.run([sys.executable, '-c',
                               "from matr1x import " +
                               "util;print(util" +
                               ".grab_system_information(" +
                               str(self.systems) + "))"],
                              capture_output=True)
        # print information string
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
        self.system_list.setEnabled(True)
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
        self.system_list.setEnabled(False)
        print("### Running script now")
        # define basic part of script, imports relevant commands
        self.script = generate_script(self.systems,
                                      self.script_edit.toPlainText())
        self.thread = ExecThread(self.sample_edit.text(),
                                 self.user_edit.text(),
                                 self.script)
        self.thread.finished.connect(self.process_finished)
        logger.info("The following script was run:\n" + self.script)
        self.thread.start()
        self.abort_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.kill_button.setEnabled(True)

    def update_systems(self):
        self.systems = [item.text()
                        for item in self.system_list.selectedItems()]

    def clear_system_selection(self):
        for i in range(self.system_list.count()):
            self.system_list.item(i).setSelected(False)

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
            os.path.join(os.path.expanduser("~"), "users/"),
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
        self.update_systems()

        try:
            # get settable information to put into the header (columns/units)
            settable_info = self.get_settable_info()

            # write matrix file header
            output_file.write("# system def : " +
                              ",".join(self.systems) + "\n")
            output_file.write("# system names : " + ",".join(settable_info[1]) +
                              "\n")
            output_file.write("# system units : " + ",".join(settable_info[2]) +
                              "\n")
        except Exception:
            print("error in generating settable_info from file, telemetry "
                  "header could not be generated")
        for i, line in enumerate(self.script_edit.toPlainText().split("\n")):
            if i < 3 and "# system " in line:
                # if there are already definitions of the system, skip these
                continue
            output_file.write(line + "\n")
        output_file.close()

    def load_from_file(self):
        """
        loads the script to file, making sure that header information specified
        still agree with the corresponding system
        """
        filename = QFileDialog.getOpenFileName(
            self, 'Select Script',
            os.path.join(os.path.expanduser("~"), "users/"),
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
        self.script_edit.clear()
        self.clear_system_selection()
        settable_info = None
        for i, line in enumerate(input_file):
            if 0 == i:
                if "# system def : " in line:
                    # load system from definition in file
                    system_line = line.strip().replace(
                        "# system def : ", "")
                    for syst in system_line.split(","):
                        self.system_list.item(
                            self.system_dict[syst]).setSelected(True)
                    self.update_systems()
                    settable_info = self.get_settable_info()
                else:
                    print("No system defined in script, " +
                          "please choose system(s)")
                    print("==========\n")
            elif 1 == i:
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
            elif 2 == i:
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
