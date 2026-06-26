#!/usr/bin/env python3 
from pynput.keyboard import Key, KeyCode, Listener
import time
import threading
import pyaudio
import wave
import libtmux
from pywhispercpp.model import Model

# Source - https://stackoverflow.com/a/17673011
# Posted by Nils Werner, modified by community. See post 'Timeline' for change history
# Retrieved 2026-06-25, License - CC BY-SA 4.0

from contextlib import contextmanager
from ctypes import CFUNCTYPE, c_char_p, c_int, cdll

ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)

def py_error_handler(filename, line, function, err, fmt):
    pass

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

@contextmanager
def noalsaerr():
    asound = cdll.LoadLibrary('libasound.so')
    asound.snd_lib_error_set_handler(c_error_handler)
    yield
    asound.snd_lib_error_set_handler(None)

class Threader():
    def __init__(self):
        self.data = ["fresh"]
        self.count = 0
        self.cool = False
        self.listener = None
        self.recorder = RecordingManager()

    def start_listener(self):
        self.listener = Listener(on_press = self.on_press)
        self.listener.daemon = False
        self.listener.start()

    def on_press(self, key):
        if key == Key.ctrl_r:
            if not self.recorder.should_record:
                self.recorder.manager_start()
            else:
                self.recorder.stop()
                self.recorder.transcribe()


        if key == Key.delete: 
            return False

class RecordingManager():
    def __init__(self):
        self.recorder = threading.Thread(target=self.record, daemon=False)
        self.should_record = False
        self.transcriber = threading.Thread(target=self.transcribe, daemon=False)

    def transcribe(self):
        model = Model('base.en')
        print("Got audio, now transcribing")
        segments = model.transcribe('output.wav')

        fulltext = ''
        for segment in segments:
            fulltext += segment.text  # also fixed: you had .join() which was wrong
        server = libtmux.Server()
        claude = server.sessions[3].windows[1].panes[0]
        claude.send_keys(fulltext, enter=True)

    def record(self):
        print("Started recording")
        chunk = 1024  
        sample_format = pyaudio.paInt16  
        channels = 2
        fs = 16000  
        filename = "output.wav"

        with noalsaerr():
            p = pyaudio.PyAudio()  

        stream = p.open(format=sample_format,
                        channels=channels,
                        rate=fs,
                        frames_per_buffer=chunk,
                        input=True)

        frames = []  
        while(self.should_record):
            data = stream.read(chunk)
            frames.append(data)
        stream.stop_stream()
        stream.close()
        p.terminate()

        print('Finished recording')

        # Save the recorded data as a WAV file
        wf = wave.open(filename, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(sample_format))
        wf.setframerate(fs)
        wf.writeframes(b''.join(frames))
        wf.close()
        print('recorded audio file')

    def manager_start(self):
        self.should_record = True
        self.recorder.start()

    def stop(self):
        self.should_record = False
        self.recorder.join()
        self.recorder = threading.Thread(target=self.record, daemon=False)


threader = Threader()

print("Starting Key Listener")

threader.start_listener()



