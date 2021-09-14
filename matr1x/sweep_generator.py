"""
This module contains a gui application for the creation of sweeps for matrix
in a reasonably straight forward fashion. Heavily relies on numpy.linspace
for the creation of the sweep segments.
"""
import sys
import time
from ast import literal_eval
from math import floor
from os.path import basename, exists, expanduser, join, splitext

import pyqtgraph as pg
from numpy import linspace
from PyQt5.QtCore import QLocale, pyqtSignal
from PyQt5.QtGui import QDoubleValidator, QIntValidator
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QFileDialog, QGridLayout, QLabel, QLineEdit,
                             QPushButton, QScrollArea, QTextEdit, QVBoxLayout,
                             QWidget)

from . import systems_directory
from .gui_util import CustomViewBox
from .util import (calculate_sweep, generate_col_index, get_settable_columns,
                   merge_systems)

usersfolder = join(expanduser("~"), "users")
if exists(usersfolder) is False:
    usersfolder = expanduser("~")

# double validator that disallows comma
lo = QLocale("C")
lo.setNumberOptions(QLocale.RejectGroupSeparator)
validator = QDoubleValidator()
validator.setLocale(lo)


class LineEditFocus(QLineEdit):
    """
    Reimplements LineEdit with focusInEvent
    """
    focusIn = pyqtSignal()

    def __init__(self, parent=None, string=None):
        if string is not None:
            super().__init__(string)
        else:
            super().__init__(None)

    def focusInEvent(self, e, parent=None):
        super().focusInEvent(e)
        self.focusIn.emit()


class SweepPreviewPopup(QDialog):
    """
    Popup showing the sweep as list and as plot

    Parameters
    ------
    index : int
      index of column in sweep to be displayed on startup
    sweep : list
      list of sweeps for each column
    cols : list
      list of column names
    units :list
      list of column units
    csign : list
      list of corresponding parameter identifiers
    """

    def __init__(self, parent, index, sweep, cols, units, csign):
        super().__init__(parent)
        self.sweep = sweep
        self.cols = cols
        self.units = units
        self.csign = csign
        self.canvas = None

        # initialize ui
        grid = QGridLayout()

        closeButton = QPushButton("Close preview")
        closeButton.clicked.connect(self.closePopup)

        self.textEdit = QTextEdit()
        self.textEdit.setReadOnly(True)
        self.textEdit.setMinimumHeight(100)

        # add label to show cursor position
        self.posLabel = QLabel("x: {:e}\ny: {:e}".format(0, 0))

        # populate combo box with column names and identifiers
        comboBox = QComboBox()
        columns = []
        for c, cs in zip(self.cols, self.csign):
            columns.append(cs + " - " + c.strip())
        comboBox.addItems(columns)
        comboBox.setCurrentIndex(index)
        comboBox.currentIndexChanged.connect(self.indexChanged)

        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")
        self.vb = CustomViewBox()
        self.pw = pg.PlotWidget(viewBox=self.vb, name="plot1",
                                enableMenu=False)
        self.plt = self.pw.plot()
        self.plt.setPen((0, 0, 153), width=3)

        self.proxy = pg.SignalProxy(self.pw.scene().sigMouseMoved,
                                    rateLimit=30,
                                    slot=self.mouseMoved)

        self.plotListRangeX(index)
        self.updateTextEdit(index)

        grid.addWidget(closeButton, 0, 0)
        grid.addWidget(comboBox, 1, 0)
        grid.addWidget(self.textEdit, 2, 0, 4, 1)

        grid.addWidget(self.posLabel, 0, 1, 1, 5)
        grid.addWidget(self.pw, 1, 1, 5, 5)

        self.setLayout(grid)
        self.show()

    def indexChanged(self, newIndex):
        """
        If index is changed, show the interface for new index
        """
        self.plotListRangeX(newIndex)
        self.updateTextEdit(newIndex)

    def updateTextEdit(self, index):
        """
        Updates the textEdit to show the current sweep[index]
        """
        self.textEdit.clear()
        for index, item in zip(range(len(self.sweep[index])),
                               self.sweep[index]):
            self.textEdit.append(str(index) + "\t| " + str(item))

    def mouseMoved(self, ev):
        """
        implement event to update cursor position while pointer is in plot
        """
        mousePoint = self.vb.mapSceneToView(ev[0])
        self.posLabel.setText("x: {:e}\ny: {:e}".format(mousePoint.x(),
                                                        mousePoint.y()))

    def plotListRangeX(self, index):
        """
        Updates the plot to show sweep[index] against its range
        """
        self.pw.getAxis("left").textWidth = 0
        length = len(self.sweep[index])
        self.plt.setData(x=linspace(0, length, length),
                         y=self.sweep[index], symbol="o")

        self.pw.setLabel("bottom", "index")
        self.pw.setLabel("left", (self.cols[index].strip() + " [" +
                                  self.units[index].strip() + "]"))

    def closePopup(self):
        """
        Obvious...
        """
        self.close()


class MainWindow(QDialog):
    """
    Define main layout, runs everything

    Parameters
    ------
    system : str
      path to system(s) for which an input file should be generated
    inputcb : function handle
      callback function used to return the filename of the generated file
    """

    def __init__(self, system=None, inputcb=None):
        super().__init__()

        self.system = system
        self.inputcb = inputcb

        # sweep variables
        self.loop_over = []
        self.up_down = []
        self.repeat = []
        self.functions = []
        self.sweepParams = []
        self.systemFilename = ""

        # gui variables
        self.nRowPreview = 3
        self.labels = (("Column", "label"), ("Name", "label"),
                       ("Unit", "label"), ("Start value", "float"),
                       ("End value", "float"), ("Point count", "int"),
                       ("Append sweep", "buttonA"), ("Repeat", "int"),
                       ("Up- and down", "boolean"),
                       ("Loop over column", "combo"),
                       ("Function", "comboF"),
                       ("Preview column", "buttonP"))

        # initialize generic (system independent) part of ui
        self.outputList = None

        self.fileEdit = QLineEdit(self)
        self.fileEdit.setReadOnly(True)

        addButton = QPushButton('+ system')
        addButton.clicked.connect(self.show_file_dialog)

        delButton = QPushButton('- system')
        delButton.clicked.connect(self.delete_last_system)

        loadButton = QPushButton('Load inputfile')
        loadButton.clicked.connect(self.gui_from_sweep)

        fGrid = QGridLayout()

        fGrid.addWidget(self.fileEdit, 0, 0, 1, 10)
        fGrid.addWidget(addButton, 0, 10)
        fGrid.addWidget(delButton, 0, 11)
        fGrid.addWidget(loadButton, 0, 12)

        self.grid = QGridLayout()
        self.grid.setSpacing(5)

        self.gridUtility = QGridLayout()
        self.gridUtility.setSpacing(5)

        self.statusBar = QTextEdit(self)
        self.statusBar.setReadOnly(True)
        self.statusBar.setMinimumHeight(80)

        sGrid = QGridLayout()

        sGrid.addWidget(QLabel("Status"), 0, 0)
        sGrid.addWidget(self.statusBar, 0, 1, 1, 10)

        vBox = QVBoxLayout()
        vBox.addLayout(fGrid)
        vBox.addLayout(self.grid)
        vBox.addLayout(self.gridUtility)
        vBox.addLayout(sGrid)

        self.setLayout(vBox)

        self.setWindowTitle('sweep_generator')

        self.populated = False

    def filename_changed(self):
        """
        On filenameChanged import new system
        """
        # get new system filename
        systemFilename = self.fileEdit.text()
        if systemFilename == "":
            return
        self.systemFilename = systemFilename
        modulestr = ""
        filenames = self.systemFilename.split(",")
        try:
            self.system = merge_systems(filenames)
            for file in filenames:
                modulestr += basename(splitext(file)[0]) + ","
            self.statusBar.append("Successfully imported -- " + modulestr)
            # update gui using the system specifications
            self.import_system()
        except ImportError:
            self.statusBar.append("ImportError was raised," +
                                  "Check path to module")

    def import_system(self):
        """
        Import specified system and populate layout
        """
        if len(self.system.columns) != len(self.system.units):
            # simple sanity check
            self.statusBar.append("Lists with columns, units and settable" +
                                  "not of equal length, check system file!")
            return
        if self.populated:
            # reset layout to clean state
            self.clear_layout(self.grid)
            self.clear_layout(self.gridUtility)
            for i in range(self.nParmsUsed):
                self.grid.setColumnStretch(i+1, 0)
        # Initalize sweep lists
        self.col_sign = []
        # generate list of settable parameters
        settables, self.flat_col, self.flat_unit = get_settable_columns(
            self.system)
        for i, (settable, col) in enumerate(zip(settables,
                                                self.system.columns)):
            # add a column for each settable parameter in the system
            if settable is True:
                if isinstance(col, (tuple, list)):
                    # if parameter has multiple values, add multiple columns
                    for c in col:
                        self.col_sign.append(generate_col_index(i))
                else:
                    self.col_sign.append(generate_col_index(i))
        # populate the actual number of used parameters (fully flattened)
        self.nParmsUsed = len(self.flat_col)
        # generate empty list of list for the sweep parameters
        self.sweep_params = [[] for i in range(self.nParmsUsed)]
        for pos in range(self.nParmsUsed):
            # for each used parameter generate labels according to system
            # specifications
            self.grid.setColumnStretch(pos+1, 1)
            self.grid.addWidget(QLabel(self.col_sign[pos]),
                                1, pos+1)
            self.grid.addWidget(QLabel(self.flat_col[pos].strip()),
                                2, pos+1)
            self.grid.addWidget(QLabel(self.flat_unit[pos].strip()),
                                3, pos+1)
        self.populate_layout()
        if not self.populated:
            self.populated = True
        self.statusBar.append("Initialization of ASG completed - enjoy!")

    def populate_layout(self):
        """
        Populate sweep controls dynamically from specifications in self.labels
        """
        for col in range(self.nParmsUsed):
            for label, row in zip(self.labels, range(len(self.labels))):
                if 0 == col:
                    # first column is labels only
                    self.grid.addWidget(QLabel(label[0]), row+1, 0)
                if label[1] == "float":
                    # float entry add lineedit with double validator
                    lineEdit = LineEditFocus()
                    lineEdit.setValidator(validator)
                    lineEdit.focusIn.connect(self.populate_sweep_grid)
                    self.grid.addWidget(lineEdit, row+1, col+1)
                elif label[1] == "buttonA":
                    # adds append button
                    appendButton = QPushButton("Append")
                    appendButton.clicked.connect(self.append_sweep_col)
                    self.grid.addWidget(appendButton, row+1, col+1)
                elif label[1] == "int":
                    # int entry with int validator (maximum value 1E9)
                    lineEdit = LineEditFocus()
                    lineEdit.setValidator(QIntValidator(0, 1E9))
                    lineEdit.focusIn.connect(self.populate_sweep_grid)
                    self.grid.addWidget(lineEdit, row+1, col+1)
                elif label[1] == "boolean":
                    # boolean entry generates checkbox
                    checkBox = QCheckBox(self)
                    checkBox.pressed.connect(self.populate_sweep_grid)
                    self.grid.addWidget(checkBox, row+1, col+1)
                elif label[1] == "combo":
                    # combobox/dropdown menu
                    comboBox = QComboBox(self)
                    columns = ["None"]
                    for i in range(self.nParmsUsed):
                        columns.append(self.col_sign[i] +
                                       " - " +
                                       self.flat_col[i].strip())
                    comboBox.addItems(columns)
                    self.grid.addWidget(comboBox, row+1, col+1)
                elif label[1] == "comboF":
                    # function dropdown menu
                    comboBox = QComboBox(self)
                    columns = ["None", "sqrt", "x^2",
                               "exp", "ln", "log10", "10^x"]
                    comboBox.addItems(columns)
                    self.grid.addWidget(comboBox, row+1, col+1)
                elif label[1] == "buttonP":
                    previewButton = QPushButton("Preview")
                    previewButton.clicked.connect(self.preview_sweep)
                    self.grid.addWidget(previewButton, row+1, col+1)

        # generate sweep grid labels and layout
        self.currentCol = QLabel("Selected Column - \nStart - Stop - Points")

        self.sweepGrid = QGridLayout()

        # set layout and box containing sweep grid, required for
        # straightforward deletion/reinitialization
        self.baseBox = QVBoxLayout()
        self.baseBox.addLayout(self.sweepGrid)
        self.baseBox.addStretch(1)

        baseArea = QWidget(self)
        baseArea.setLayout(self.baseBox)

        scrollArea = QScrollArea(self)
        scrollArea.setWidget(baseArea)
        scrollArea.setWidgetResizable(True)

        self.sweepBox = QVBoxLayout()
        self.sweepBox.addWidget(self.currentCol)
        self.sweepBox.addWidget(scrollArea)

        self.sweepPreview = QTextEdit(self)
        self.sweepPreview.setReadOnly(True)
        genButton = QPushButton("Generate Sweep")
        genButton.clicked.connect(self.print_sweep_to_preview)

        self.fileEditOutput = QLineEdit(self)

        fileButtonOutput = QPushButton("Select Output")
        fileButtonOutput.clicked.connect(self.show_file_dialog_output)

        self.appendCheckbox = QCheckBox("Append to file")

        outputButton = QPushButton("Output to file")
        outputButton.clicked.connect(self.output_to_file)

        self.gridUtility.addWidget(genButton, 0, 0)
        self.gridUtility.addWidget(outputButton, 6, 0)
        self.gridUtility.addWidget(self.fileEditOutput, 6, 1, 1, 4)
        self.gridUtility.addWidget(fileButtonOutput, 6, 5)
        self.gridUtility.addWidget(self.appendCheckbox, 6, 6)

        self.gridUtility.addLayout(self.sweepBox, 0, 5, 6, 2)
        self.gridUtility.addWidget(self.sweepPreview, 0, 1, 6, 4)
        # make the column with the preview and the textedit to take all
        # available space
        self.gridUtility.setColumnStretch(1, 1)
        self.gridUtility.setColumnStretch(5, 1)

    def preview_sweep(self):
        """
        Display a popup with the sweep given in the column (as plot and list)
        """
        col = self.grid.getItemPosition(self.grid.indexOf(self.sender()))[1]
        sweep = self.generate_sweep()
        if sweep is None:
            return
        elif isinstance(sweep, str):
            # if an error is encountered during the generation of the sweep
            # lists from the parameter, a helpful error message should be
            # provided here
            self.statusBar.append(sweep)
            return
        popup = SweepPreviewPopup(self, col-1, sweep, self.flat_col,
                                  self.flat_unit, self.col_sign)
        popup.show()

    def print_sweep_to_preview(self):
        """
        Print the complete set of sweeps to self.sweepPreview
        """
        sweep = self.generate_sweep()
        if sweep is None:
            # sweep generation failed
            return
        elif isinstance(sweep, str):
            # if an error is encountered during the generation of the sweep
            # lists from the parameter, a helpful error message should be
            # provided here
            self.statusBar.append(sweep)
            return
        # get length of longest sweep and
        # make sure all sweeps in a group are of equal length
        # this is how the looping over different column is implemented here
        maxLen = []
        for i in range(len(sweep)):
            # make sure that values that belong to the same parameter have the
            # same length
            if ((self.col_sign[i] == self.col_sign[i-1] and
                 len(sweep[i]) != len(sweep[i-1]))):
                self.statusBar.append("Not all parameters for that " +
                                      "instrument have the same length\n" +
                                      "Please correct your sweep params " +
                                      "in instrument " + self.col_sign[i] +
                                      " -> " + self.flat_col[i] +
                                      "\nIf a parameter accepts multiple "
                                      "values, the different values for that "
                                      "parameter must have the same length")
                return
            maxLen.append(len(sweep[i]))

        # get the maximum length
        maxLen = max(maxLen)

        # calculate necessary multiplicators to stretch the sweeps
        # if sweep lenghts are not multiples of each other something is wrong
        mult = []
        for i in range(len(sweep)):
            if [] == sweep[i]:
                mult.append(0)
            elif maxLen % len(sweep[i]):
                self.statusBar.append("sweep_params seem unsuitable for "
                                      "measurements, lengths not multiples. "
                                      "Check that loops are set correctly.")
                return
            else:
                mult.append(maxLen/len(sweep[i]))

        self.sweepPreview.clear()
        # initialize outputList, here the strings for the lines will be input
        # this is equivalent to what goes into the file
        self.outputList = []
        for i in range(maxLen):
            string = []
            for j, swp in enumerate(sweep):
                if 0 != mult[j] and not i % mult[j]:
                    # here the values are stretched to the correct "length" if
                    # the loop_over parameter is considered
                    if self.col_sign[j] == self.col_sign[j-1] and len(sweep) > 1:
                        # Parameter has multiple values
                        string.append(str(swp[floor(i/mult[j])]))
                    else:
                        # Parameter has single value
                        string.append(
                            "-" + self.col_sign[j] +
                            " " + str(swp[floor(i/mult[j])]))
                string.append("   ")
            # add everything into a single string
            string = "".join(string)
            # add at most 1000 characters per line
            self.sweepPreview.append(string[:1000])
            # replace excess spaces from file and print, could be removed
            self.outputList.append(string.replace("   ", " ") + "\n")
        return 1

    def output_to_file(self):
        """
        Write the contents of self.outputList to the file specified for output
        """
        append = self.appendCheckbox.checkState()
        filename = self.fileEditOutput.text()
        if "" == filename:
            self.statusBar.append("Please define a filename")
            return
        elif "" == self.systemFilename:
            self.statusBar.append("System undefined")
            return
        else:
            if self.print_sweep_to_preview() is None:
                return
            # append .nt if not already in filename and update textEdit
            match = "." + str(self.nParmsUsed) + "t"
            if match not in filename:
                filename += match
                self.fileEditOutput.setText(filename)
            try:
                outputFile = open(filename, 'r')
            except (OSError, IOError):
                self.statusBar.append("File does not exist yet, adding header")
                append = 0
            try:
                if 2 == append:
                    # user wants to append
                    outputFile = open(filename, 'a')
                else:
                    outputFile = open(filename, 'w')
            except (OSError, IOError):
                self.statusBar.append("File can not be opened")
                return
        # get telemtry and append to file
        if 2 != append:
            timestamp = time.strftime("%a, %d %b %Y %H:%M:%S \n",
                                      time.localtime())
            outputFile.write("# Input file for matrix program generated by" +
                             " sweep_generator")
            outputFile.write("\n# System filename : ")
            outputFile.write(self.systemFilename)
            outputFile.write("\n# Settable columns : ")
            outputFile.write(",".join(self.flat_col))
            outputFile.write("\n# Settable units : ")
            outputFile.write(",".join(self.flat_unit))
            outputFile.write("\n# Settable column label : ")
            outputFile.write(",".join(self.col_sign))
            outputFile.write("\n# params : ")
            outputFile.write(str(self.sweep_params))
            outputFile.write("\n# loop_over : ")
            outputFile.write(str(self.loop_over))
            outputFile.write("\n# functions : ")
            outputFile.write(str(self.functions))
            outputFile.write("\n# up_down : ")
            outputFile.write(str(self.up_down))
            outputFile.write("\n# repeat : ")
            outputFile.write(str(self.repeat))
            outputFile.write("\n# Time stamp : ")
            outputFile.write(timestamp)
        for line in self.outputList:
            outputFile.write(line)
        outputFile.close()
        if self.inputcb is not None:
            self.inputcb(filename)
        if 2 == append:
            self.statusBar.append("Output appended to " + filename + " at " +
                                  timestamp)
        else:
            self.statusBar.append("Output written to " + filename + " at " +
                                  timestamp)

    def append_sweep_col(self):
        """
        Add defined sweep parameters to self.sweep_params and populate sweepGrid

        Take care that whenever adressing the list (i.e. sweep_params) that
        those are shifted by 1 (layout starts at col 1, lists at 0)
        """
        position = self.grid.getItemPosition(self.grid.indexOf(self.sender()))
        param_set = []

        for i in range(3):
            # get set of values for linspace -> linspace(p1, p2, p3)
            param_set.append(self.grid.itemAtPosition(
                position[0]-(3-i), position[1]).widget().text())

        if "" in param_set:
            self.statusBar.append("Missing value, " +
                                  "please specify all three parameters")
            return
        else:
            # add the list of three parameters to the sweep_params for the
            # given column
            self.sweep_params[position[1]-1].append(param_set)
            for i in range(3):
                # clear widgets with the original values, as these are now
                # appended to the sweep_params
                self.grid.itemAtPosition(position[0]-(3-i),
                                         position[1]).widget().setText("")
            # update the sweep grid for the active column (should now display
            # the new parameter set)
            self.populate_sweep_grid(position[1])

    def remove_sweep_param(self, col):
        """
        removes a set of linspace parameters from sweep_params
        at the correct position
        """
        row = self.sweepGrid.getItemPosition(
            self.sweepGrid.indexOf(self.sender()))[0]
        del self.sweep_params[col-1][row]
        self.populate_sweep_grid(col)

    def populate_sweep_grid(self, col=None):
        if col is None:
            try:
                col = self.grid.getItemPosition(
                    self.grid.indexOf(self.sender()))[1]
            except AttributeError:
                self.statusBar("No sender could be found, check function calls"
                               "in source code, populate_sweep_grid got probably"
                               "called without col parameter by a direct"
                               "function call")
                return
        self.currentCol.setText("Selected Column:\t" +
                                self.col_sign[col-1] + " -- " +
                                str(self.flat_col[col-1]).strip() +
                                "\nStart - Stop - Points")

        # Clear Widget
        self.clear_layout(self.sweepGrid)

        row = 0
        for param_set in self.sweep_params[col-1]:
            for i in range(3):
                le = QLineEdit(self)
                le.setText(str(param_set[i]))
                if 3 == i:
                    le.setValidator(QIntValidator(0, 1E09))
                else:
                    le.setValidator(validator)
                le.editingFinished.connect(
                    lambda: self.change_sweep_param(col))
                self.sweepGrid.addWidget(le, row, i)
            qpb = QPushButton("Delete")
            # Fun Function :), parameter calls lambda, which calls
            # self.remove_sweep_param(col), because connect can pass no parameters
            # directly, feels quite dirty but seems to work
            qpb.clicked.connect(lambda: self.remove_sweep_param(col))
            self.sweepGrid.addWidget(qpb, row, 3)
            row += 1

    def change_sweep_param(self, col):
        """
        Changes the sweep param if it is manipulated within the sweepGrid
        """
        text = self.sender().text()
        position = self.sweepGrid.getItemPosition(
            self.sweepGrid.indexOf(self.sender()))
        self.sweep_params[col-1][position[0]][position[1]] = text

    def clear_layout(self, layout):
        """
        Clears all child widgets from layout
        """
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            else:
                self.clear_layout(item)

    def show_file_dialog(self):
        """
        Opens a QFileDialog with filter system*.py
        """
        # get filenames from dialog
        filename = QFileDialog.getOpenFileName(
            self, 'Select system file', systems_directory,
            "system files (system*.py)")[0]
        if "" == filename:
            return
        # requires system names not to include a ,
        if "" == self.fileEdit.text():
            systems = []
        else:
            systems = self.fileEdit.text().split(",")
        # append new system to the end
        systems.append(filename)
        # set text and update system definition
        self.fileEdit.setText(",".join(systems))
        self.filename_changed()

    def delete_last_system(self):
        """
        Removes last system from system fileEdit
        """
        systems = self.fileEdit.text().split(",")
        # remove last system
        if 0 < len(systems):
            systems.pop()
        else:
            return
        # set text and update system definition
        self.fileEdit.setText(",".join(systems))
        self.filename_changed()

    def show_file_dialog_output(self):
        """
        Opens a QFileDialog with filter "." + self.nParms + "t"

        could be used to implement forced good practice naming the input files
        i.e. adding system and date to filename
        """
        filename = QFileDialog.getSaveFileName(self, 'Select output file',
                                               usersfolder,
                                               str(self.nParmsUsed) +
                                               't file (*.' +
                                               str(self.nParmsUsed) + 't)')
        self.fileEditOutput.setText(filename[0])

    def generate_sweep(self):
        """
        GUI functionality to populate all lists necessary for sweep generation
        After that generates the sweep from the parameters (still needs to be
        stretched)
        """
        self.loop_over = []
        self.functions = []
        self.up_down = []
        self.repeat = []
        for row, label in zip(range(len(self.labels)), self.labels):
            for col in range(self.nParmsUsed):
                currentWidget = self.grid.itemAtPosition(row+1, col+1).widget()
                if "combo" == label[1] and "Loop" in label[0]:
                    self.loop_over.append(currentWidget.currentIndex()-1)
                elif "comboF" == label[1] and "Function" in label[0]:
                    self.functions.append(currentWidget.currentText())
                elif "boolean" == label[1] and "Up" in label[0]:
                    self.up_down.append(currentWidget.checkState())
                elif "int" == label[1] and "Repeat" in label[0]:
                    try:
                        text = currentWidget.text()
                        if "" == text:
                            self.repeat.append(1)
                        else:
                            self.repeat.append(int(text))
                    except TypeError:
                        self.statusBar.append("Type Error called by repeat," +
                                              "should not happen")
                        return

        # all lists are up to date, now generate sweep lists
        sweep = calculate_sweep(self.sweep_params, self.loop_over.copy(),
                                self.up_down, self.repeat, self.functions)
        if sweep is None:
            self.statusBar.append("Error during sweep generation, " +
                                  "check that all loops are set correctly")
            return
        return sweep

    def gui_from_sweep(self):
        """
        Opens a QFileDialog with filter ".xxxt", where x is a number
        """
        # get filename from dialog
        filename = QFileDialog.getOpenFileName(
            self, 'Select input file', usersfolder,
            "t files (*.*t)")[0]
        # load system from file, define read out parameters to parse
        params = {"# params : ": None, "# loop_over : ": None,
                  "# functions : ": None, "# up_down : ": None,
                  "# repeat : ": None}
        with open(filename, "r") as infile:
            for line in infile:
                if "# System" in line:
                    line = line.strip().replace("# System filename : ", "")
                    self.fileEdit.setText(line)
                    self.filename_changed()
                for key in params.keys():
                    if key in line:
                        # read the parameters from the corresponding line
                        line = line.strip().replace(key, "")
                        params[key] = literal_eval(line)

        if None in params.values():
            # not all parameters could be read from the file
            return
        else:
            (self.sweep_params, self.loop_over, self.functions, self.up_down,
             self.repeat) = params.values()

        # initialize layout with values specified in file
        for row, label in zip(range(len(self.labels)), self.labels):
            for col in range(self.nParmsUsed):
                currentWidget = self.grid.itemAtPosition(row+1, col+1).widget()
                if "combo" == label[1] and "Loop" in label[0]:
                    currentWidget.setCurrentIndex(self.loop_over[col]+1)
                elif "comboF" == label[1] and "Function" in label[0]:
                    currentWidget.setCurrentText(self.functions[col])
                elif "boolean" == label[1] and "Up" in label[0]:
                    currentWidget.setCheckState(self.up_down[col])
                elif "int" == label[1] and "Repeat" in label[0]:
                    if 1 == self.repeat[col]:
                        currentWidget.setText("")
                    else:
                        currentWidget.setText(str(self.repeat[col]))


def main():
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())
