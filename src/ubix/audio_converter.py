from pywhispercpp.model import Model
import pyaudio
import threading
import wave
import os
import logging
import importlib.resources

pkg_root = importlib.resources.files("ubix")

logger = logging.getLogger(__name__)

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

class AudioConverter():
    def __init__(self):
        self.recorder = threading.Thread(target=self.record, daemon=False)
        self.should_record = False
        self.transcriber = threading.Thread(target=self.transcribe, daemon=False)

    def transcribe(self):
        model = Model('base.en')
        logger.info("Transcribing audio file")
        segments = model.transcribe(pkg_root / 'output.wav')

        audio_text = ''
        for segment in segments:
            audio_text += segment.text  
        #server = libtmux.Server()
        #claude = server.sessions[3].windows[0].panes[0]
        #claude.send_keys(fulltext, enter=True)
        if os.path.exists(pkg_root / 'output.wav'):
            os.remove(pkg_root / 'output.wav')

        logger.info(f'Transcribed text: {audio_text}')
        return audio_text

    def record(self):
        logger.info("Started recording")
        chunk = 1024  
        sample_format = pyaudio.paInt16  
        channels = 2
        fs = 16000  
        filename = pkg_root / "output.wav"

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

        logger.info('Finished recording')

        # Save the recorded data as a WAV file
        wf = wave.open(filename, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(sample_format))
        wf.setframerate(fs)
        wf.writeframes(b''.join(frames))
        wf.close()
        logger.info('Audio File Written')

    def start_recording(self):
        self.should_record = True
        self.recorder.start()

    def stop_recording(self):
        self.should_record = False
        self.recorder.join()
        self.recorder = threading.Thread(target=self.record, daemon=False)
