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
"""Helpers for LakeShore devices in control GUIs."""

from typing import Any

import numpy
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGridLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTableView,
)

from matr1x import usersfolder


class SelectLakeshoreInput(QDialog):
    """
    Open a dialog for selecting a sensor calibration curve for the Lakeshore temperature controller.

    This dialog allows the user to choose from a list of available calibration curves
    for the Lakeshore temperature controller. It displays the curve numbers and names,
    and allows the user to set the selected curve for the controller.

    Attributes
    ----------
    curves : dict
        A dictionary of available calibration curves, where keys are
        curve numbers and values are curve names.
    activeCurve : int
        The currently active curve number.
    curvesList : QListWidget
        A widget displaying the list of available curves.
    """

    def __init__(self, parent, lakeshore_dev):
        super().__init__(parent)
        if not hasattr(lakeshore_dev, "getCurveNumber"):
            raise AttributeError(f"Device {lakeshore_dev} does not support 'getCurveNumber")
        self._dev = lakeshore_dev
        # read input curves
        self.curves = {}
        for i in range(1, 60):
            self.curves[i] = self._dev.getCurveName(i)
        self.activeCurve = self._dev.getCurveNumber()
        self.initUI()
        self.show()

    def initUI(self):
        """Initialize GUI for popup."""
        self.setWindowTitle("Select Lakeshore input curve")
        grid = QGridLayout()

        self.curvesList = QListWidget()
        self.curvesList.addItems([f"{k}: {v}" for k, v in self.curves.items()])
        self.curvesList.setCurrentRow(self.activeCurve - 1)

        cancelButton = QPushButton("Cancel")
        cancelButton.clicked.connect(self.close)

        setCurveButton = QPushButton("Set")
        setCurveButton.clicked.connect(self.set_curve)

        grid.addWidget(self.curvesList, 0, 0, 10, -1)
        grid.addWidget(cancelButton, 10, 0)
        grid.addWidget(setCurveButton, 10, 1)
        self.setLayout(grid)

    def set_curve(self):
        """
        Set the selected calibration curve for the Lakeshore temperature controller.

        This method reads the selected curve from the QListWidget, sets
        it on the Lakeshore device if possible, and closes the dialog.
        """
        selectedcurve = int(self.curvesList.currentItem().text().split(":")[0])
        if hasattr(self._dev, "setCurveNumber"):
            self._dev.setCurveNumber(selectedcurve)
        self.close()


class TableModel(QAbstractTableModel):
    """
    A table model for displaying PID parameters.

    This model is designed to work with a 2D numpy array containing
    PID parameters and related data.

    Parameters
    ----------
    data : numpy.ndarray
        A 2D numpy array containing the data to be displayed in the table.
    """

    def __init__(self, data: numpy.ndarray) -> None:
        super().__init__()
        self._data = data

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        """
        Return the data stored under the given role for the item referred to by the index.

        Parameters
        ----------
        index : QModelIndex | QPersistentModelIndex
            The index of the requested data.
        role : int
            The role for which the data is requested.

        Returns
        -------
        Any
            The requested data as a string if the role is DisplayRole, None otherwise.
        """
        if role == Qt.ItemDataRole.DisplayRole:
            value = self._data[index.row(), index.column()]
            return str(value)
        return None

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        """
        Return the number of rows in the model.

        Parameters
        ----------
        parent : QModelIndex | QPersistentModelIndex
            The parent index (unused in this implementation).

        Returns
        -------
        int
            The number of rows in the data.
        """
        return self._data.shape[0]

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        """
        Return the number of columns in the model.

        Parameters
        ----------
        parent : QModelIndex | QPersistentModelIndex
            The parent index (unused in this implementation).

        Returns
        -------
        int
            The number of columns in the data.
        """
        return self._data.shape[1]

    def headerData(self, section: int, orientation: Qt.Orientation, role: int) -> str | None:  # type: ignore our issue #1601
        """
        Return the header data.

        Do that for the given role and section in the header with the
        specified orientation.

        Parameters
        ----------
        section : int
            The section number for which the header data is required.
        orientation : Qt.Orientation
            The orientation of the header (horizontal or vertical).
        role : int
            The role for which the data is requested.

        Returns
        -------
        str or None
            The header data as a string if the conditions are met, QVariant() otherwise.
        """
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if section == 0:
                return "T (K)"
            elif section == 1:
                return "P"
            elif section == 2:
                return "I"
            elif section == 3:
                return "D"
            elif section == 4:
                return "Heater range"
        return None


class WriteLakeshoreZonePID(QDialog):
    """
    Dialog to select a PID parameter table for use with the ZONE mode.

    The PID parameter file must be a text file which contains columns for:
    the upper temperature of the zones, P, I, D parameters, and heater range.
    A total of 10 entries are allowed.

    This dialog provides functionality to load a PID table from a file,
    display it in a table view, and write the parameters to the Lakeshore device.
    """

    def __init__(self, parent, lakeshore_dev=None):
        super().__init__(parent)
        self._dev = lakeshore_dev
        self.initUI()
        self.show()

    def initUI(self):
        """Initialize GUI for popup."""
        self.setWindowTitle("Select Lakeshore input curve")
        grid = QGridLayout()

        self.fileEdit = QLineEdit(self)
        self.fileEdit.setReadOnly(True)

        loadButton = QPushButton("Load PID Table")
        loadButton.clicked.connect(self.load_pid_table)

        grid.addWidget(self.fileEdit, 0, 0, 1, 2)
        grid.addWidget(loadButton, 0, 3)

        self.table = QTableView()
        # self.table.setReadOnly(True)
        grid.addWidget(self.table, 1, 0, 10, -1)

        self.writeButton = QPushButton("Write Table to Device")
        self.writeButton.clicked.connect(self.write_zone_to_device)
        self.writeButton.setEnabled(False)
        cancelButton = QPushButton("Cancel")
        cancelButton.clicked.connect(self.close)

        grid.addWidget(cancelButton, 12, 0)
        grid.addWidget(self.writeButton, 12, 1)

        self.setLayout(grid)

    def load_pid_table(self):
        """
        Load a PID table from a file and display it in the table view.

        This method opens a file dialog for the user to select a PID
        table file, loads the data from the file, creates a TableModel
        with the data, and sets it as the model for the table view. If
        the loaded data has the correct shape, it enables the write
        button.
        """
        filename = QFileDialog.getOpenFileName(
            self, "Select PID table file", str(usersfolder), "calibration file (*.*)"
        )[0]
        self.fileEdit.setText(filename)
        if filename != "":
            self.data = numpy.loadtxt(filename, unpack=True)
            self.model = TableModel(self.data.T)
            self.table.setModel(self.model)
            if len(self.data.shape) == 2 and self.data.shape[0] == 5:
                # if entries found enable write button
                self.writeButton.setEnabled(True)

    def write_zone_to_device(self):
        """
        Write the loaded PID table to the Lakeshore device.

        This method checks if the Lakeshore device has a 'writeZonePID'
        method. If it does, it calls this method with the loaded PID
        data as arguments. After writing the data (or if the method
        doesn't exist), it closes the dialog.
        """
        if hasattr(self._dev, "writeZonePID"):
            self._dev.writeZonePID(*self.data)
        self.close()
