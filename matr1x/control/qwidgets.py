# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# AnimatedToggle adapted from
# https://www.pythonguis.com/tutorials/pyqt6-animated-widgets/
# licensed under MIT-license
# ---
import warnings

try:
    from PyQt6.QtCore import (QEasingCurve, QPoint, QPointF, QPropertyAnimation,
                              QRectF, QSize, Qt, pyqtProperty, pyqtSlot)
    from PyQt6.QtGui import QBrush, QColor, QPainter, QPaintEvent, QPen
    from PyQt6.QtWidgets import QCheckBox, QProgressBar, QPushButton
except ImportError:
    warnings.warn("PyQt5 support will be removed in 2024. Switch to PyQt6",
                  DeprecationWarning)
    from PyQt5.QtCore import (QEasingCurve, QPoint, QPointF, QPropertyAnimation,
                              QRectF, QSize, Qt, pyqtProperty, pyqtSlot)
    from PyQt5.QtGui import QBrush, QColor, QPainter, QPaintEvent, QPen
    from PyQt5.QtWidgets import QCheckBox, QProgressBar, QPushButton


class AnimatedToggle(QCheckBox):
    # This text is included pursuant to the obligations of this upstream licence
    # and must be retained in any derivatives of this class.
    # This specific class may be used under the terms of the MIT-license:
    # Permission is hereby granted, free of charge, to any person obtaining a
    # copy of this software and associated documentation files (the “Software”),
    # to deal in the Software without restriction, including without limitation
    # the rights to use, copy, modify, merge, publish, distribute, sublicense,
    # and/or sell copies of the Software, and to permit persons to whom the
    # Software is furnished to do so, subject to the following conditions:
    #
    # The above copyright notice and this permission notice shall be included in
    # all copies or substantial portions of the Software.
    #
    # THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
    # THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    # FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    # DEALINGS IN THE SOFTWARE.
    """
    Animated toggle switch used for GuiDict activation/deactivation.

    Code was adapted from
    https://www.pythonguis.com/tutorials/pyqt6-animated-widgets
    """
    _transparent_pen = QPen(Qt.GlobalColor.transparent)
    _light_grey_pen = QPen(Qt.GlobalColor.lightGray)

    def __init__(self,
                 parent=None,
                 bar_color=Qt.GlobalColor.gray,
                 checked_color="#00B0FF",
                 handle_color=Qt.GlobalColor.white,
                 ):
        super().__init__(parent)

        # Save our properties on the object via self, so we can access them later
        # in the paintEvent.
        self._bar_brush = QBrush(bar_color)
        self._bar_checked_brush = QBrush(QColor(checked_color).lighter())

        self._handle_brush = QBrush(handle_color)
        self._handle_checked_brush = QBrush(QColor(checked_color))

        # Setup the rest of the widget.
        self.setContentsMargins(0, 0, 0, 0)
        self._handle_position = 0

        self.animation = QPropertyAnimation(self, b"handle_position", self)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setDuration(200)  # time in ms

        self.stateChanged.connect(self.setup_animation)

    def sizeHint(self):
        return QSize(32, 20)

    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)

    @pyqtSlot(int)
    def setup_animation(self, value):
        self.animation.stop()
        if value:
            self.animation.setEndValue(1)
        else:
            self.animation.setEndValue(0)
        self.animation.start()

    def paintEvent(self, e: QPaintEvent):

        contRect = self.contentsRect()
        handleRadius = round(0.44 * contRect.height())

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setPen(self._transparent_pen)
        barRect = QRectF(
            0, 0,
            contRect.width() - handleRadius, 0.70 * contRect.height()
        )
        barRect.moveCenter(QPointF(contRect.center()))
        rounding = barRect.height() / 2

        # the handle will move along this line
        trailLength = contRect.width() - 2 * handleRadius

        xPos = contRect.x() + handleRadius + trailLength * self._handle_position

        if self.isChecked():
            p.setBrush(self._bar_checked_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setBrush(self._handle_checked_brush)

        else:
            p.setBrush(self._bar_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setPen(self._light_grey_pen)
            p.setBrush(self._handle_brush)

        p.drawEllipse(
            QPointF(xPos, barRect.center().y()),
            handleRadius, handleRadius)

        p.end()

    @pyqtProperty(float)
    def handle_position(self):
        return self._handle_position

    @handle_position.setter
    def handle_position(self, pos):
        """change the property
        we need to trigger QWidget.update() method, either by:
            1- calling it here [ what we doing ].
            2- connecting the QPropertyAnimation.valueChanged() signal to it.
        """
        self._handle_position = pos
        self.update()


class matr1xProgressBar(QProgressBar):
    """
    overload Progressbar to make it better suite the needs to show values in
    the range between -5 and 105. Values outside that range are indicated by a
    red color
    """

    def __init__(self):
        super().__init__()
        self.setRange(-5, 105)
        self.setFormat("%v")

    def setValue(self, value):
        if value > self.maximum() or value < self.minimum():
            # change color
            self.reset()
            self.setStyleSheet("QProgressBar"
                               "{"
                               "background-color : red;"
                               "}")
        else:
            self.setStyleSheet("QProgressBar"
                               "{"
                               "}")

        super().setValue(value)


class ToggleButton(QPushButton):
    """
    custom QPushButton to emulate a proper toggle button (including the change
    of the button's label upon pushing)
    """

    def __init__(self, *args, **kwargs):
        if isinstance(args[0], (list, tuple)):
            label = args[0][0]
        else:
            label = args[0]
        super().__init__(label, **kwargs)
        self._labels = args[0]
        self.setCheckable(True)

    def setChecked(self, state):
        """
        change label of toggle button
        """
        super().setChecked(state)
        # if it is checked
        if isinstance(self._labels, (list, tuple)):
            if state:
                self.setText(self._labels[1])
            # if it is unchecked
            else:
                self.setText(self._labels[0])
