#!/usr/bin/env python3
from pynput.keyboard import Key, KeyCode, Listener
from ubix.audio_converter import AudioConverter
import os
import logging
import httpx
import importlib.resources

pkg_root = importlib.resources.files("ubix")

logger = logging.getLogger(__name__)

SERVER_URL = os.environ.get("UBIX_SERVER", "http://127.0.0.1:4096")


class Dictator():
    def __init__(self):
        #keyboard event listener
        self.listener = None
        self._left_ctrl_pressed = False
        self._shift_pressed = False
        #audio recorder and transcriber, loads the whisper models up front
        self.audio_converter = AudioConverter()
        #talks to ubix-server instead of running the tools itself
        self.http = httpx.Client(base_url=SERVER_URL, timeout=5)

    def send_status(self, status):
        #best effort: a missed status update must never stop a recording
        try:
            self.http.post("/client/status", json={"status": status}).raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f'could not send status {status}: {e}')

    def send_prompt(self, text):
        self.http.post("/session/prompt", json={"text": text}).raise_for_status()

    def shutdown(self):
        logger.info('Dictator Shutting Down')
        if self.audio_converter.should_record:
            self.audio_converter.stop_recording()
            self.send_status("idle")
        self.audio_converter.shutdown()
        self.http.close()

    def start_listener(self):
        self.listener = Listener(on_press = self.on_press, on_release = self.on_release)
        self.listener.daemon = False
        self.listener.start()
        return self.listener

    def toggle_recording(self):
        if not self.audio_converter.should_record:
            self.send_status("rec")
            self.audio_converter.start_recording()
            return
        self.send_status("trans")
        command = self.audio_converter.stop_recording()
        if not command.strip():
            self.send_status("idle")
            return
        try:
            #server publishes message.user + session.status exec from here on
            self.send_prompt(command)
        except httpx.HTTPError as e:
            logger.error(f'ubix-server unreachable at {SERVER_URL}, dropped command {command!r}: {e}')

    def on_press(self, key):
        if key == Key.ctrl_l:
            self._left_ctrl_pressed = True
        if key in (Key.shift, Key.shift_l, Key.shift_r):
            self._shift_pressed = True

        if self._left_ctrl_pressed and self._shift_pressed and key in (KeyCode.from_char('d'), KeyCode.from_char('D')):
            self.shutdown()
            return False

        if key == Key.ctrl_r:
            try:
                self.toggle_recording()
            except Exception as e:
                logger.exception(e)

    def on_release(self, key):
        if key == Key.ctrl_l:
            self._left_ctrl_pressed = False
        if key in (Key.shift, Key.shift_l, Key.shift_r):
            self._shift_pressed = False


def main():
    logging.basicConfig(format='%(asctime)s %(message)s', filename=pkg_root / 'dictator.log', level=logging.INFO)
    logger.info('Dictator Booting...')
    dictator = Dictator()
    listener = dictator.start_listener()
    try:
        listener.join()
    except Exception:
        logger.exception('pynput listener crashed')
        raise


if __name__ == '__main__':
    main()
