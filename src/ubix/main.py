#!/usr/bin/env python3  
from pynput.keyboard import Key, KeyCode, Listener
from ubix.tool_runner import ToolRunner
from ubix.audio_converter import AudioConverter
from enum import StrEnum, Enum
import threading
import os
import subprocess
import json
import tempfile
import logging
import importlib.resources

pkg_root = importlib.resources.files("ubix")

logger = logging.getLogger(__name__)
fifo_path = "/tmp/ubix"
for name in logging.root.manager.loggerDict:
    print(name)


def build_mode_json():
    input_path = pkg_root / "modes.txt"  # path to the text file to read

    with open(input_path, "r", encoding="utf-8") as f:
        description = f.read().strip()

    return [
        {
            "type": "function",
            "function": {
                "name": "choose_mode",
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["sys_admin", "accountant"],
                        }
                    },
                    "required": ["mode"],
                },
            },
        }
    ]

STATUS_PATH = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "ubix", "status.json"
)
os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)

class Mode(StrEnum):
    sys_admin = "ADMIN"
    accountant = "ACCT"
    scribe = "SCRIBE"

class Status(Enum):
    idle = "idle"
    recording = "rec"
    transcribing = "trans"
    executing = "exec"
    off = "off"

def write_status(data, path=STATUS_PATH):
    dir_ = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f)
    os.replace(tmp_path, path)


class Conductor():
    def __init__(self):
        #keyboard event listener
        self.key_listener = None
        self._ctrl_pressed = False
        self._left_ctrl_pressed = False
        self._shift_pressed = False
        #audio recorder and transcriber
        self.audio_converter = AudioConverter()
        #llm tool coordinator
        self.tool_runner = ToolRunner()
        self.mode = self.tool_runner.get_mode()
        self.status = { "mode": Mode["sys_admin"], "status": Status.idle.value}
        write_status(self.status)
        self.ubox_init()
        #create the hidden alacritty window

    def shutdown(self):
        logger.info('Ubix Shutting Down')
        try:
            os.remove(fifo_path)
            os.remove('output.wav')
        except FileNotFoundError:
            pass  # already gone, nothing to do
        self.change_status(Status.off)
        #send shutdown signal to alacritty window


    def change_mode(self, mode_string):
        self.status['mode'] = Mode[mode_string]
        write_status(self.status)

    def change_status(self, status):
        self.status['status'] = status.value
        write_status(self.status)

    def start_listener(self):
        self.listener = Listener(on_press = self.on_press, on_release = self.on_release)
        self.listener.daemon = False
        self.listener.start()
        return self.listener

    def ubox_init(self):
        #create the fifo, create the ubix window
        #write 'Welcome to Ubix, press Alt+Shift+u to minimize this window'
        if not os.path.exists(fifo_path):
            os.mkfifo(fifo_path)

        alacritty_cmd = "alacritty --class floatterm --config-file /home/will/.config/alacritty/floatterm.toml -e tail -f /tmp/ubix"
        cmd_list = alacritty_cmd.split(" ")
        result = subprocess.Popen(cmd_list)

        with open(fifo_path, "w") as fifo:
            fifo.write("Ubix> Welcome to Ubix\n")
            fifo.write("Ubix> Press right ctrl to give a command, press Alt+Shift+u to hide this window\n")
            fifo.write("User>")

    def ubox_input(self, input):
        with open(fifo_path, "w") as fifo:
            fifo.write(f'{input}\n')
            fifo.write("Ubix>")

    def ubox_output(self, output):
        with open(fifo_path, "w") as fifo:
            fifo.write(f'{output}\n')
            fifo.write("Ubix>")

    def on_press(self, key):
        if key == Key.ctrl_l:
            self._left_ctrl_pressed = True
        if key in (Key.shift, Key.shift_l, Key.shift_r):
            self._shift_pressed = True

        if self._left_ctrl_pressed and self._shift_pressed and key in (KeyCode.from_char('d'), KeyCode.from_char('D')):
            self.shutdown()
            return False

        if key == Key.ctrl_r:
            self._ctrl_pressed = True
            try:
                if not self.audio_converter.should_record:
                    self.change_status(Status.recording)
                    self.audio_converter.start_recording()
                else:
                    #every line here is sequential, each will finish before running
                    #next line
                    command = self.audio_converter.stop_recording()
                    self.ubox_input(command)
                    #here write the command as User> 'command'
                    self.change_status(Status.executing)
                    self.ubox_output('executing...')
                    result = self.tool_runner.execute(command)

                    logger.info(f'execution result: {result}')
                    self.ubox_output(result.response)
                    self.change_status(Status.idle)
                    self.change_mode(self.tool_runner.get_mode())
            except Exception as e:
                logger.exception(e)
                self.ubox_output("There was an exception in CTRL_R if block")
            finally: 
                self.change_status(Status.idle)

    def on_release(self, key):
        if key == Key.ctrl_r:
            self._ctrl_pressed = False
        if key == Key.ctrl_l:
            self._left_ctrl_pressed = False
        if key in (Key.shift, Key.shift_l, Key.shift_r):
            self._shift_pressed = False

def main():
    logging.basicConfig(format='%(asctime)s %(message)s', filename=pkg_root / 'ubix.log', level=logging.INFO)
    logger.info('Ubix Booting...')
    conductor = Conductor()
    listener = conductor.start_listener()
    try:
        listener.join()
    except Exception:
        logger.exception('pynput listener crashed')
        raise   

if __name__ == '__main__':
    main()

