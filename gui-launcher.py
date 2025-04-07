#!/usr/bin/env python3

import sys

from ansi2html import Ansi2HTMLConverter
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5 import QtCore

# import sys
import time
import os

finished_timeout = 15  # default, set to -1 for no timeout (manual quit)


def if_mac_set_menubar_title(title):
    if sys.platform.startswith("darwin"):
        # Set app name, if PyObjC is installed
        # Python 2 has PyObjC preinstalled
        # Python 3: pip3 install pyobjc-framework-Cocoa
        try:
            from Foundation import NSBundle

            bundle = NSBundle.mainBundle()
            if bundle:
                app_name = title
                app_info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                if app_info:
                    app_info["CFBundleName"] = app_name
        except ImportError:
            pass


class ProcessOutputReader(QProcess):
    produce_output = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    # self.timeout_finish_time = 0.0

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # merge stderr channel into stdout channel
        # self.setProcessChannelMode(QProcess.MergedChannels)
        self.setProcessChannelMode(QProcess.SeparateChannels)

        # prepare decoding process' output to Unicode
        codec = QTextCodec.codecForLocale()
        self._decoder_stdout = codec.makeDecoder()
        # only necessary when stderr channel isn't merged into stdout:
        # self._decoder_stderr = codec.makeDecoder()

        self.readyReadStandardOutput.connect(self._ready_read_standard_output)
        # only necessary when stderr channel isn't merged into stdout:
        self.readyReadStandardError.connect(self._ready_read_standard_error)

    @pyqtSlot()
    def _ready_read_standard_output(self):
        raw_bytes = self.readAllStandardOutput()
        text = self._decoder_stdout.toUnicode(raw_bytes)

        self.produce_output.emit(text)

    # only necessary when stderr channel isn't merged into stdout:
    @pyqtSlot()
    def _ready_read_standard_error(self):
        raw_bytes = self.readAllStandardError()
        text = self._decoder_stderr.toUnicode(raw_bytes)
        self.produce_output.emit(text)

    # def terminateMe(self):
    #     print ("terminating process")
    #     super().kill()


class MyConsole(QTextEdit):
    def __init__(self, parent=None):
        self.__init__(parent=parent, timeout=int(finished_timeout))

    def __init__(self, timeout, parent=None):
        super().__init__(parent=parent)

        self.close_on_finished_timeout = timeout
        self.counting_down_finished = False

        self.setFont(QFont("ProFontIIx Nerd Font Mono", 14))
        self.setFixedHeight(int(myHeight))
        self.setFixedWidth(int(myWidth))

        self.setWindowOpacity(0.8)
        # self.setWindowFlags(QtCore.Qt.FramelessWindowHint)

        self.setStyleSheet("background-color: rgb(0, 0, 0); color: rgb(200,200,200);")

        self.setReadOnly(True)
        #        self.setMaximumBlockCount(10000)  # limit console to 10000 lines

        self._cursor_output = self.textCursor()

        self.conv = Ansi2HTMLConverter(inline=True, scheme="dracula")

    def setTimeout(self, t):
        self.close_on_finished_timeout = float(t)

    @pyqtSlot(str)
    def append_output(self, text):
        tmp_newline = "///   #===newline===#   ///\n"
        html = self.conv.convert(text, full=False, ensure_trailing_newline=True)
        html = html.replace(" ", "&nbsp;").replace("\n", "<br />")

        self._cursor_output.insertHtml(html)
        # self._cursor_output.insertText(html)

        self.scroll_to_last_line()

    def append_plaintext(self, text):
        self._cursor_output.insertText(text)

    def scroll_to_last_line(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        # cursor.movePosition(QTextCursor.Up if cursor.atBlockStart() else
        # QTextCursor.StartOfLine)
        self.setTextCursor(cursor)

    # @pyqtSlot(str)
    def handleFinished(self, exitcode):
        self.setVisible(True)
        self.show()
        self.showNormal()
        self.raise_()
        self.setFocus()

        if str(exitcode) == "0":
            exitmoji = "🟢"
        else:
            exitmoji = "🔴"

        self.append_output(
            "\n{} Console got finished signal {}".format(exitmoji, exitcode)
        )

        if not wait_on_finished:
            self.append_output("\nClosing in ")

            proc_finish_time = time.time()
            self.timeout_finish_time = proc_finish_time + self.close_on_finished_timeout
            count_seconds = 0.0

            self.counting_down_finished = True

            while (
                time.time() < self.timeout_finish_time and self.counting_down_finished
            ):
                if time.time() >= proc_finish_time + count_seconds:
                    remain_seconds = int(self.close_on_finished_timeout - count_seconds)
                    self.append_plaintext("{}..".format(remain_seconds))
                    count_seconds = count_seconds + 1.0

                app.processEvents()

            if self.counting_down_finished:
                app.quit()

    def exitGracefully(self):
        print("attempting to exit gracefully")
        # self.timeout_finish_time = 0.0
        self.close_on_finished_timeout = 0.0
        reader.kill()
        sys.exit(0)
        # app.quit()

    def closeEvent(self, event):
        print("window closed, attempting to quit")
        self.exitGracefully()

    def keyPressEvent(self, event):
        if event.key() == 81:  # Q to quit
            print("key press {}: attempting to exit".format(event.key()))
            self.exitGracefully()
        elif event.key() in [72, 77]:  # H or M to minimize
            print("key press {}: attempting to minimize".format(event.key()))
            self.showMinimized()
        elif event.key() == 32:  # spacebar to pause
            if self.counting_down_finished:
                self.counting_down_finished = False
                self.append_output("\n👆[Q] to close\n")
            else:
                if reader.state == QProcess.Suspended:
                    self.append_output("\n▶️ resuming process\n")
                    reader().resume()
                else:
                    self.append_output("\n⏸ attempting to suspend process\n")
                    reader.suspend()
        else:
            print("ignoring key press {}".format(event.key()))

    def hideEvent(self, event):
        self.showMinimized()

        # keyPressEvent defined in child


#        self.keyPressed.emit(event) # Emit is hidden in child


cmd_line_args = sys.argv
launcher_executable = cmd_line_args.pop(0)  # this is the python executable,
# which we don't want.
# prog_args = cmdLineArgs

### get switches ###
if cmd_line_args[0].startswith("-t"):
    _ = cmd_line_args.pop(0)
    finished_timeout = int("".join(filter(str.isdigit, cmd_line_args.pop(0))))

cmd_arg = cmd_line_args.pop(0)
if cmd_arg == "--wait":
    wait_on_finished = True
    gui_executable = cmd_line_args.pop(0)
else:
    wait_on_finished = False
    gui_executable = cmd_arg

# application_name = os.path.splitext(gui_executable)[0]
application_name = gui_executable.split("/")[-1]

print(
    "attempting to launch: {} with args: {} as {}".format(
        gui_executable, cmd_line_args, application_name
    )
)

if_mac_set_menubar_title(application_name)

# create the application instance
app = QApplication(sys.argv)
screensize = app.primaryScreen().size()
myWidth = screensize.width() / 2
myHeight = screensize.height() * 2 / 3

# create a process output reader
reader = ProcessOutputReader()

# create a console and connect the process output reader to it
console = MyConsole(finished_timeout)
reader.produce_output.connect(console.append_output)
reader.finished.connect(console.handleFinished)


def userQuit():
    console = None
    reader.kill()
    sys.exit(0)


app.aboutToQuit.connect(console.exitGracefully)

reader.start(gui_executable, cmd_line_args)  # start the process
console.setWindowTitle(application_name)
console.show()  # make the console visible
app.exec_()  # run the PyQt main loop
