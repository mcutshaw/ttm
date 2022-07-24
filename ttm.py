import sys
from PySide6 import QtCore, QtWidgets, QtGui
import tomli
from functools import partial
from PySide6.QtWidgets import QDialogButtonBox, QVBoxLayout, QLabel
import json
from datetime import datetime
import os
import logging
from tempfile import NamedTemporaryFile
from shutil import copy


def attrsetter(attr):
    def set_any(self, value):
        self.d[attr] = value
        self.d['history'].append((str(datetime.now()), attr))
        self.save()

    return set_any

def attrgetter(attr):
    def get_any(self):
        return self.d[attr]

    return get_any


class DataRecorder:
    interrupts = property(fset=attrsetter("interrupts"), fget=attrgetter("interrupts"))
    short_breaks = property(
        fset=attrsetter("short_breaks"), fget=attrgetter("short_breaks")
    )
    long_breaks = property(
        fset=attrsetter("long_breaks"), fget=attrgetter("long_breaks")
    )
    successful_periods = property(
        fset=attrsetter("successful_periods"), fget=attrgetter("successful_periods")
    )

    def __init__(self, file_path):
        self.file_path = file_path
        self.load()

    def load(self):
        self.d = None
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path) as f:
                    self.d = json.load(f)
            except Exception as e:
                logging.exception(e)

        if self.d is None:
            self.d = {
                "interrupts": 0,
                "short_breaks": 0,
                "long_breaks": 0,
                "successful_periods": 0,
                "history": [],
            }

    def save(self):
        with NamedTemporaryFile('w+') as f:
            json.dump(self.d, f)
            f.flush()
            copy(f.name, self.file_path)


class TaskEndedDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Period Ended")

        QBtn = QDialogButtonBox.No | QDialogButtonBox.Yes

        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        message = QLabel("Task Ended")
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


class TaskTimeManager(QtWidgets.QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.datarecorder = DataRecorder(config["track_file"])

        self.suc_periods = 0
        self.dlg = TaskEndedDialog()
        self.timer_screen = QtWidgets.QLabel("00:00", alignment=QtCore.Qt.AlignCenter)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.timerEvent)
        self.timerisstarted = False
        self.timer_type = None

        self.standby = True
        self.starttbutton = (QtWidgets.QPushButton("Start Task"), "task_period")
        self.shortbbutton = (QtWidgets.QPushButton("Short Break"), "short_break")
        self.longbbutton = (QtWidgets.QPushButton("Long Break"), "long_break")

        self.interruptbutton = (QtWidgets.QPushButton("Interrupt"), "interrupt")

        self.standby_buttons = [self.starttbutton, self.shortbbutton, self.longbbutton]
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.addWidget(self.timer_screen)

        self.all_buttons = self.standby_buttons + [self.interruptbutton]
        for button, button_type in self.all_buttons:
            self.layout.addWidget(button)
            button.clicked.connect(partial(self.buttonEvent, button_type))

        self.interruptbutton[0].hide()

        self.timer_screen.setText("00:00")

    def starttimer(self, seconds):
        self.cur_time = QtCore.QTime(0, int(seconds / 60), seconds % 60)
        self.timer.start(1000)
        self.timer_screen.setText(self.cur_time.toString("mm:ss"))

    @QtCore.Slot()
    def timerEvent(self):
        if not self.timerisstarted:
            return
        elif self.cur_time.second() + self.cur_time.minute() * 60 == 0:
            self.timerended()
        else:
            self.cur_time = self.cur_time.addSecs(-1)
            time_text = self.cur_time.toString("mm:ss")
            self.timer_screen.setText(time_text)

    def timerended(self):
        success = self.dlg.exec()
        if self.timer_type == "task_period":
            if success:
                self.datarecorder.successful_periods += 1
                self.suc_periods += 1
            else:
                self.datarecorder.interrupts += 1
                self.suc_periods = 0
            if self.suc_periods == self.config["periods_before_long"]:
                self.suc_periods = 0
                self.timer_type = "long_break"
                self.starttimer(self.config["long_break"])
            else:
                self.timer_type = "short_break"
                self.starttimer(self.config["short_break"])
        else:
            if self.timer_type == "":
                self.datarecorder.short_break += 1
            elif self.timer_type == "long_break":
                self.datarecorder.long_breaks += 1
            self.timer_type = "task_period"
            self.starttimer(self.config["task_period"])

        # prompt dialog box
        # track response for long break/data
        # move to next stage.

    def buttonEvent(self, button_type):
        if button_type == "interrupt":
            self.toggle_standby()
            self.suc_periods = 0
            self.datarecorder.interrupts += 1
        else:
            self.timer_type = button_type
            self.toggle_standby()
            self.starttimer(self.config[button_type])

    def toggle_standby(self):
        if self.standby:
            for button, button_type in self.standby_buttons:
                button.hide()
            self.interruptbutton[0].show()
            self.timerisstarted = True

        else:
            for button, button_type in self.standby_buttons:
                button.show()
            self.interruptbutton[0].hide()
            self.timerisstarted = False
        self.standby = not self.standby


if __name__ == "__main__":

    with open("config.toml", "rb") as f:
        config = tomli.load(f)
    app = QtWidgets.QApplication()
    size = config["size"]
    widget = TaskTimeManager(config)
    widget.resize(*size)
    widget.show()
    sys.exit(app.exec())
