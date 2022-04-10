# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
"""
This module contains gui related functions that are required by the sweep
generator and matrix_gui
"""
import pyqtgraph as pg
from PyQt5.QtCore import QObject, Qt, pyqtSignal


class CustomViewBox(pg.ViewBox):
    """
    Reimplements the pyqthgraph ViewBox and improves its usability with the
    mouse.
    Behavior is as follows:

      right click autoscales graph
      ---
      mouse inside plot:
      left drag zooms to rectangle
      right drag allows panning plot
      mouse wheel zooms in/out with cursor position defining center
      ---
      mouse on x or y axis:
      left button drags corresponding axis
      right button allows panning individual axis
      mouse wheel zooms in/out with cursor position deifning center
    """

    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        self.setMouseMode(self.RectMode)

    # reimplement right-click to autoscale plot
    def mouseClickEvent(self, ev):
        if ev.button() == Qt.RightButton:
            self.autoRange()
            # set autorange upon change of data
            self.enableAutoRange()
        # elif ev.button() == Qt.MidButton:
        #     self.raiseContextMenu(ev)

    # reimplement drag event
    def mouseDragEvent(self, ev, axis=None):
        if ev.button() in (Qt.RightButton, Qt.MidButton):
            # enable pan mode
            self.setMouseMode(self.PanMode)
            pg.ViewBox.mouseDragEvent(self, ev, axis)
            self.setMouseMode(self.RectMode)
        elif ev.button() == Qt.LeftButton and axis is not None:
            # enable pan mode on individual axis
            self.setMouseMode(self.PanMode)
            pg.ViewBox.mouseDragEvent(self, ev, axis)
            self.setMouseMode(self.RectMode)
        else:
            pg.ViewBox.mouseDragEvent(self, ev, axis)


class EmittingStream(QObject):
    """
    Stream to communicate between the threads
    """
    name = "GUIStream"
    text_written = pyqtSignal(str)

    def write(self, text):
        self.text_written.emit(str(text))

    def flush(self):
        pass
